"""Portable hardware selection, account preflight, reuse, and safe repair."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from molecule_studio.mlip import environment, setup


def test_hardware_choices_are_per_machine_and_failed_queries_are_not_no_gpu(monkeypatch):
    monkeypatch.setattr(environment, 'sys', SimpleNamespace(platform='linux'))
    monkeypatch.setattr(environment.shutil, 'which', lambda name: 'nvidia-smi')
    response = SimpleNamespace(returncode=0, stdout='0, Example GPU, 610.00, 12288, GPU-example\n', stderr='')
    monkeypatch.setattr(environment.subprocess, 'run', lambda *a, **k: response)
    info = environment.hardware()
    assert info['gpus'][0]['name'] == 'Example GPU'
    assert environment.choose_device('auto', info) == 'cuda'
    assert environment.choose_device('cpu', info) == 'cpu'
    response.stdout = ''
    assert environment.choose_device('auto', environment.hardware()) == 'cpu'
    response.returncode = 1
    response.stderr = 'Driver not accessible'
    with pytest.raises(ValueError, match='Could not check'):
        environment.choose_device('auto', environment.hardware())
    with pytest.raises(ValueError):
        environment.choose_device('cuda', {'gpus': [], 'note': 'No NVIDIA driver'})


def test_missing_driver_and_macos_choose_cpu(monkeypatch):
    monkeypatch.setattr(environment.shutil, 'which', lambda name: None)
    monkeypatch.setattr(Path, 'is_file', lambda _: False)
    assert environment.choose_device('auto') == 'cpu'
    monkeypatch.setattr(environment, 'sys', SimpleNamespace(platform='darwin'))
    assert environment.choose_device('auto') == 'cpu'
    assert 'macOS' in environment.hardware()['note']


def test_probe_accepts_cuda_build_suffix_and_explains_cpu_build(monkeypatch):
    class Tensor:
        def __mul__(self, other): return self
        def sum(self): return self
        def cpu(self): return 2
    cuda = SimpleNamespace(is_available=lambda: True, synchronize=lambda: None,
                           get_device_name=lambda: 'Test NVIDIA GPU')
    torch = SimpleNamespace(__version__='2.13.0+cu130', version=SimpleNamespace(cuda='13.0'),
                            cuda=cuda, ones=lambda *a, **k: Tensor())
    monkeypatch.setitem(sys.modules, 'torch', torch)
    monkeypatch.setitem(sys.modules, 'sella', SimpleNamespace(Sella=object, IRC=object))
    import importlib
    original = importlib.import_module
    monkeypatch.setattr(importlib, 'import_module', lambda name, *a: object() if name == 'aimnet.calculators' else original(name, *a))
    versions = {'aimnet': '0.2.0', 'torch': '2.13.0+cu130', 'ase': '3.29.0', 'sella': '2.6.0'}
    monkeypatch.setattr(environment.importlib.metadata, 'version', lambda name: versions.get(name, '1.0'))
    result = environment.probe('aimnet2')
    assert result['ready'] and result['devices'] == ['cpu', 'cuda']
    torch.version.cuda = None
    cuda.is_available = lambda: False
    result = environment.probe('aimnet2')
    assert result['ready'] and result['devices'] == ['cpu']
    assert 'CPU-only' in result['cuda_error']


def test_catalogue_selection_is_explicit():
    assert len(setup.select_models('all')) == len(setup.CATALOGUE)
    assert setup.select_models('none') == []
    names = setup.select_models('aimnet2,aimnet2-wb97m-d3_0')
    assert len(names) == 4 and len(set(names)) == 4
    with pytest.raises(ValueError): setup.select_models('imaginary-model')


@pytest.fixture
def fake_setup(tmp_path, monkeypatch):
    root = tmp_path / 'model data'
    root.mkdir()
    calls = []
    existing = root / 'existing-python'
    existing.touch()
    setup.atomic_json(root / 'environments.json', {'aimnet2': {'python': str(existing)}})
    monkeypatch.setattr(setup, 'cached', lambda root, name, **kw: True)
    def worker(python, root, action, config=None, **kwargs):
        calls.append((action, str(python), config))
        if action == 'probe':
            return {'ready': True, 'devices': ['cpu'] if Path(python) == existing else ['cpu', 'cuda'], 'sella': True}
        return {'ready': True, 'sha256': 'a' * 64}
    def install(root, backend, emit, cancelled, **kwargs):
        calls.append(('install', backend, kwargs))
        path = Path(kwargs['target'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return str(path)
    monkeypatch.setattr(setup, 'worker_action', worker)
    monkeypatch.setattr(setup, 'managed_environment', install)
    return SimpleNamespace(root=root, calls=calls, existing=existing, worker=worker)


def test_cached_setup_reuses_environment_and_skips_huggingface(fake_setup, monkeypatch):
    t = fake_setup
    monkeypatch.setattr(setup, 'check_access', lambda *a: pytest.fail('Unexpected login'))
    assert setup.run_setup(t.root, ['aimnet2-wb97m-d3_0', 'aimnet2-nse_0'], 'cpu', emit=lambda _: None)
    assert [c[0] for c in t.calls] == ['probe', 'check', 'check']
    assert setup.read_json(t.root / 'setup-state.json')['completed']


def test_cpu_environment_is_replaced_for_cuda_only_after_real_check(fake_setup):
    t = fake_setup
    assert setup.run_setup(t.root, ['aimnet2-wb97m-d3_0'], 'cuda', emit=lambda _: None)
    entry = setup.read_json(t.root / 'environments.json')['aimnet2']
    assert entry['python'] != str(t.existing)
    assert entry['previous_python'] == str(t.existing)
    assert entry['preferred_device'] == 'cuda'
    assert t.existing.is_file()
    assert [c[0] for c in t.calls] == ['probe', 'install', 'probe', 'check']


def test_failed_gpu_model_preserves_the_working_registration(fake_setup, monkeypatch):
    t = fake_setup
    def fail_check(*args, **kwargs):
        if args[2] == 'check': raise RuntimeError('GPU out of memory')
        return t.worker(*args, **kwargs)
    monkeypatch.setattr(setup, 'worker_action', fail_check)
    assert not setup.run_setup(t.root, ['aimnet2-wb97m-d3_0'], 'cuda', emit=lambda _: None)
    assert setup.read_json(t.root / 'environments.json')['aimnet2']['python'] == str(t.existing)
    assert setup.read_json(t.root / 'setup-state.json')['models']['aimnet2-wb97m-d3_0']['status'] == 'needs_attention'


def test_repeated_repairs_preserve_all_previous_environments(fake_setup):
    t = fake_setup
    paths = {str(t.existing)}
    for _ in range(3):
        assert setup.run_setup(t.root, ['aimnet2-wb97m-d3_0'], 'cuda', repair=True, emit=lambda _: None)
        path = setup.read_json(t.root / 'environments.json')['aimnet2']['python']
        assert path not in paths
        paths.add(path)
    assert all(Path(path).is_file() for path in paths)


def test_check_only_never_installs_cuda(fake_setup):
    t = fake_setup
    assert not setup.run_setup(t.root, ['aimnet2-wb97m-d3_0'], 'cuda', check_only=True, emit=lambda _: None)
    assert [c[0] for c in t.calls] == ['probe']


def test_account_access_is_checked_before_package_installs(fake_setup, monkeypatch):
    t = fake_setup
    monkeypatch.setattr(setup, 'cached', lambda root, name, **kw: False)
    def denied(*args):
        t.calls.append(('access',))
        raise ValueError('Account has no access hf_EXAMPLESECRET')
    monkeypatch.setattr(setup, 'check_access', denied)
    assert not setup.run_setup(t.root, ['uma-s-1p2'], 'cpu', accepted=['uma-s-1p2'], emit=lambda _: None)
    assert t.calls == [('access',)]
    assert 'hf_EXAMPLESECRET' not in (t.root / 'setup-state.json').read_text()


def test_missing_consent_does_not_download_or_authenticate(fake_setup, monkeypatch):
    t = fake_setup
    monkeypatch.setattr(setup, 'cached', lambda root, name, **kw: False)
    monkeypatch.setattr(setup, 'check_access', lambda *a: pytest.fail('Missing consent'))
    assert not setup.run_setup(t.root, ['uma-s-1p2'], 'cpu', emit=lambda _: None)
    assert not t.calls


def test_cancellation_preserves_existing_configuration(fake_setup):
    t = fake_setup
    with pytest.raises(InterruptedError):
        setup.run_setup(t.root, ['aimnet2-wb97m-d3_0'], 'cuda', cancelled=lambda: True)
    assert setup.read_json(t.root / 'environments.json')['aimnet2']['python'] == str(t.existing)


def test_cli_without_stdin_requires_explicit_choices(monkeypatch):
    from molecule_studio import setup_cli
    monkeypatch.setattr(setup_cli.sys, 'stdin', SimpleNamespace(isatty=lambda: False))
    with pytest.raises(SystemExit) as error:
        setup_cli.main([])
    assert error.value.code == 2


def test_corrupt_weights_require_explicit_repair(tmp_path, monkeypatch):
    def corrupt(*args):
        raise ValueError('Checksum mismatch')
    monkeypatch.setattr(setup, 'model_path', corrupt)
    with pytest.raises(ValueError, match='Checksum'):
        setup.cached(tmp_path, 'MACE-ANI-CC')
    assert not setup.cached(tmp_path, 'MACE-ANI-CC', repair=True)


def test_cached_gated_model_needs_no_login_or_new_consent(fake_setup, monkeypatch):
    monkeypatch.setattr(setup, 'check_access', lambda *a: pytest.fail('Cached UMA must work offline'))
    assert setup.run_setup(fake_setup.root, ['uma-s-1p2'], 'cpu', emit=lambda _: None)


def test_unavailable_gated_model_does_not_block_public_models(fake_setup, monkeypatch):
    monkeypatch.setattr(setup, 'cached', lambda root, name, **kw: name != 'uma-s-1p2')
    assert not setup.run_setup(fake_setup.root, ['uma-s-1p2', 'aimnet2-wb97m-d3_0'], 'cpu', emit=lambda _: None)
    state = setup.read_json(fake_setup.root / 'setup-state.json')
    assert state['models']['uma-s-1p2']['status'] == 'needs_attention'
    assert state['models']['aimnet2-wb97m-d3_0']['status'] == 'ready'


def test_native_guided_walkthrough_in_isolated_qt_process():
    pytest.importorskip('PySide6')
    import os
    import subprocess
    script = Path(__file__).with_name('guided_setup_smoke.py')
    result = subprocess.run([sys.executable, '-m', 'pytest', str(script), '-q', '-p', 'no:cacheprovider'],
                            env=os.environ | {'QT_QPA_PLATFORM': 'offscreen'},
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
