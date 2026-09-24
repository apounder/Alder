"""Shared, resumable setup used by the terminal and desktop walkthroughs."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from .environment import (atomic_json, external_environment, external_libraries,
                          managed_environment, managed_python, redact)
from .offline import bundle_directory
from .registry import CATALOGUE, model_path

RECOMMENDED = ['aimnet2-wb97m-d3_0', 'MACE-ANI-CC']
ACCESS_URL = 'https://huggingface.co/facebook/UMA'
TOKEN_URL = 'https://huggingface.co/settings/tokens'
_core_app = None


def data_root():
    global _core_app
    from PySide6.QtCore import QCoreApplication, QStandardPaths
    if QCoreApplication.instance() is None:
        _core_app = QCoreApplication([])
        _core_app.setApplicationName('Alder')
    return Path(os.environ.get('ALDER_MLIP_HOME') or
                str(Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'calculations-v1'))


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


def select_models(text):
    names = []
    for item in text.replace(',', ' ').split():
        if item == 'recommended':
            selected = RECOMMENDED
        elif item == 'all':
            selected = list(CATALOGUE)
        elif item == 'none':
            selected = []
        elif item in ('aimnet2', 'mace', 'uma'):
            selected = [name for name, spec in CATALOGUE.items() if spec['backend'] == item]
        elif item.isdigit() and 1 <= int(item) <= len(CATALOGUE):
            selected = [list(CATALOGUE)[int(item) - 1]]
        elif item in CATALOGUE:
            selected = [item]
        else:
            raise ValueError(f'Unknown model: {item}. Use --list to see available models.')
        names.extend(n for n in selected if n not in names)
    if not text.strip():
        raise ValueError('Choose at least one model, or none for the viewer only.')
    return names


def licensed(name):
    return CATALOGUE[name]['backend'] == 'uma' or name.startswith('MACE-OFF23')


def model_config(name, device):
    spec = CATALOGUE[name]
    return dict(backend=spec['backend'], checkpoint=name, device=device,
                precision='float64' if spec['backend'] == 'mace' else 'float32',
                task=spec['task'], head=spec['head'], corrections='checkpoint')


def cached(root, name, *, repair=False):
    try:
        model_path(model_config(name, 'cpu'), Path(root) / 'models')
        return True
    except FileNotFoundError:
        return False
    except ValueError:
        if repair:
            return False
        raise


@contextmanager
def setup_lock(root, *, in_app=False):
    from PySide6.QtCore import QLockFile
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    locks = []
    try:
        for filename in (['setup.lock'] if in_app else ['queue.lock', 'setup.lock']):
            lock = QLockFile(str(root / filename))
            if not lock.tryLock(0):
                raise ValueError('Close other Alder windows and setup commands, then retry.')
            locks.append(lock)
        from .store import Store
        from .environment import process_alive
        store = Store(root / 'jobs.sqlite')
        try:
            for job in store.jobs():
                worker = store.artifact(job['id'], 'worker') if job['status'] == 'running' else None
                if worker and process_alive(worker.get('pid')):
                    raise ValueError('A calculation is running. Wait for it to finish before changing model environments.')
        finally:
            store.close()
        yield
    finally:
        for lock in reversed(locks):
            lock.unlock()


def worker_action(python, root, action, config=None, *, backend=None, emit=print, cancelled=lambda: False):
    """Use the real worker protocol; isolate temporary files from the GUI's checks."""
    with tempfile.TemporaryDirectory(prefix='setup-', dir=root) as folder:
        folder = Path(folder)
        report = folder / 'result.json'
        args = [str(python), str(Path(__file__).with_name('worker.py')), action, '--result', str(report)]
        if backend:
            args += ['--backend', backend]
        if config is not None:
            source = folder / 'model.json'
            atomic_json(source, config)
            args += ['--config', str(source), '--cache', str(Path(root) / 'models')]
        if action == 'download':
            args.append('--licensed')  # run_setup has already checked per-model consent.
            bundle = bundle_directory()
            if bundle is not None:
                args += ['--bundled-cache', str(bundle / 'models')]
        with external_libraries():
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8', errors='replace',
                                       env=external_environment(),
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        try:
            while True:
                if cancelled():
                    raise InterruptedError('Setup stopped. Completed steps are saved; run setup again to continue.')
                try:
                    output, _ = process.communicate(timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
        if output.strip():
            emit(redact(output.strip()))
        result = read_json(report)
        if process.returncode or result.get('error'):
            raise RuntimeError(result.get('error') or f'{action} failed; see the setup log above.')
        if not result:
            raise RuntimeError(f'{action} returned no result.')
        return result


def check_access(names, token=None):
    """Check the exact gated files before installing any calculator packages."""
    from huggingface_hub import get_hf_file_metadata, get_token, hf_hub_url, login
    if token:
        login(token=token, add_to_git_credential=False)
    if not get_token():
        raise ValueError(f'A Hugging Face read token is required. Create one at {TOKEN_URL}; request model access at {ACCESS_URL}.')
    for name in names:
        spec = CATALOGUE[name]
        get_hf_file_metadata(hf_hub_url(spec['repo'], spec['file'], revision=spec['revision']), timeout=20)


def run_setup(root, names, device, *, accepted=(), token=None, repair=False,
              check_only=False, emit=print, cancelled=lambda: False):
    """Caller holds setup_lock. Register replacements only after real inference."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if device not in ('cpu', 'cuda'):
        raise ValueError('Resolve automatic hardware selection before installing.')
    if any(name not in CATALOGUE for name in names):
        raise ValueError('Select models from the supported catalogue.')
    config = read_json(root / 'environments.json')
    state = read_json(root / 'setup-state.json')
    state.update(selection=list(names), device=device, completed=False)
    state.setdefault('models', {})
    state.setdefault('licences', {})
    for name in accepted:
        if name in CATALOGUE and licensed(name):
            state['licences'][name] = CATALOGUE[name]['license']
    def save():
        atomic_json(root / 'setup-state.json', state)
    def stop():
        if cancelled():
            raise InterruptedError('Setup stopped. Run it again to continue.')
    save()
    errors = {}
    needed = []
    # Preflight every selection before the first large environment download.
    for name in names:
        stop()
        try:
            present = cached(root, name, repair=repair)
            if not present and licensed(name) and not check_only and state['licences'].get(name) != CATALOGUE[name]['license']:
                raise ValueError('Licence acknowledgement is needed. Rerun the walkthrough and accept this model’s terms.')
            if not present and CATALOGUE[name]['backend'] == 'uma' and not check_only:
                needed.append(name)
        except (ValueError, OSError) as error:
            errors[name] = redact(error)
    if needed:
        emit('Checking Hugging Face access before downloading calculation packages…')
        try:
            check_access(needed, token)
        except Exception as error:
            for name in needed:
                errors[name] = f'Hugging Face access check failed: {redact(error)}. Check your token and model approval at {ACCESS_URL}.'
    token = None
    ready_envs = {}
    failed_backends = {}
    for name in names:
        stop()
        backend = CATALOGUE[name]['backend']
        if name in errors:
            state['models'][name] = dict(status='needs_attention', error=errors[name], device=device)
            emit(f'{name}: {errors[name]}')
            save()
            continue
        try:
            if backend in failed_backends:
                raise RuntimeError(failed_backends[backend])
            if backend not in ready_envs:
                old = config.get(backend, {}).get('python', '')
                python = old
                probe = {}
                if old and Path(old).is_file() and (not repair or check_only):
                    emit(f'{backend}: checking the existing environment…')
                    try:
                        probe = worker_action(old, root, 'probe', backend=backend, emit=emit, cancelled=cancelled)
                    except RuntimeError as error:
                        emit(str(error))
                if not probe.get('ready') or device not in probe.get('devices', []):
                    if check_only:
                        raise RuntimeError(probe.get('cuda_error') if device == 'cuda' and probe.get('cuda_error') else 'Environment needs setup or repair. Run alder-setup.')
                    pending = state.setdefault('pending_environments', {})
                    key = backend + '-' + device
                    python = None if repair else pending.get(key)
                    if not python or not Path(python).resolve().is_relative_to(root.resolve()) or python == old:
                        target = managed_python(root, backend, device)
                        # Do not overwrite an active environment or an earlier backup.
                        # Explicit repair also avoids reusing a damaged partial install.
                        if target.parent.parent.exists():
                            target = root / (target.parent.parent.name + '-' + uuid.uuid4().hex[:8]) / target.parent.name / target.name
                        python = str(target)
                    pending[key] = python
                    save()
                    emit(f'{backend}: installing {device.upper()} packages. This can take several minutes…')
                    try:
                        python = managed_environment(root, backend, emit, cancelled, device=device, target=python)
                        probe = worker_action(python, root, 'probe', backend=backend, emit=emit, cancelled=cancelled)
                        if not probe.get('ready') or device not in probe.get('devices', []):
                            reason = probe.get('cuda_error') or '; '.join(probe.get('errors', [])) or f'{device.upper()} could not be verified.'
                            if device == 'cuda':
                                reason += ' Update the NVIDIA driver and retry, or choose CPU in setup.'
                            raise RuntimeError(reason)
                    except InterruptedError:
                        raise
                    except Exception as error:
                        failed_backends[backend] = redact(error)
                        raise
                ready_envs[backend] = (python, probe)
            python, probe = ready_envs[backend]
            selection = model_config(name, device)
            state['models'][name] = dict(status='checking' if check_only else 'installing', device=device)
            save()
            if not cached(root, name, repair=repair):
                if check_only:
                    raise ValueError('Weights are missing. Run the setup walkthrough to download them.')
                emit(f'{name}: downloading and verifying model weights…')
                worker_action(python, root, 'download', selection, emit=emit, cancelled=cancelled)
            emit(f'{name}: running a real energy/force calculation on {device.upper()}…')
            result = worker_action(python, root, 'check', selection, emit=emit, cancelled=cancelled)
            if not result.get('ready'):
                raise RuntimeError('Model calculation did not pass.')
            entry = config.setdefault(backend, {})
            if entry.get('python') and entry['python'] != python:
                entry['previous_python'] = entry['python']
            entry.update(python=python, probe=probe, preferred_device=device, last_ready_model=selection)
            atomic_json(root / 'environments.json', config)
            state.get('pending_environments', {}).pop(backend + '-' + device, None)
            state['models'][name] = dict(status='ready', device=device, python=python,
                                        sha256=result['sha256'], sella=bool(probe.get('sella')))
            emit(f'{name}: READY on {probe.get("gpu", "GPU") if device == "cuda" else "CPU"}.')
            if not probe.get('sella'):
                emit('Transition-state and IRC calculations need Sella repair; other checked calculations are available.')
        except InterruptedError:
            save()
            raise
        except Exception as error:
            errors[name] = redact(error)
            state['models'][name] = dict(status='needs_attention', device=device, error=errors[name])
            emit(f'{name}: NEEDS ATTENTION — {errors[name]}')
        save()
    state['completed'] = not errors
    save()
    emit('Setup complete.' if not errors else 'Setup is incomplete. Working models are saved; rerun setup to retry the listed problems.')
    return not errors
