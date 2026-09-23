"""Windows offline kit: standalone Python, local wheels and pinned public weights."""
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile
from .registry import checksum


def bundle_directory():
    override=os.environ.get('MOLECULE_STUDIO_OFFLINE_BUNDLE')
    directory=Path(override) if override else Path(sys.executable).parent/'mlip-offline'
    if override or directory.exists():return directory
    return None


def manifest(directory):
    data=json.loads((Path(directory)/'manifest.json').read_text(encoding='utf-8'))
    if data.get('format')!=1 or data.get('platform')!='win-amd64':
        raise ValueError('Unsupported offline calculation bundle.')
    return data


def verified_file(directory, data, name):
    path=Path(directory)/name
    if name not in data['files'] or not path.is_file() or checksum(path)!=data['files'][name]:
        raise ValueError(f'Offline bundle is incomplete or corrupt: {name}. Download/extract the complete MLIP Offline edition again.')
    return path


def extract_python(archive, target, cancelled):
    """Only Python files from a verified archive; reject links/traversal."""
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if cancelled():raise InterruptedError('Offline setup cancelled. Run setup again to continue.')
            p=PurePosixPath(item.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in item.filename or ':' in item.filename or (item.external_attr>>16)&0o170000==0o120000:
                raise ValueError('Unsafe path in offline Python archive.')
            z.extract(item,target)


def install_environment(directory, root, backend, emit=print, cancelled=lambda:False, *, target=None):
    from .environment import ENV_VERSION, managed_python, external_environment, external_libraries
    if sys.platform!='win32' or sysconfig.get_platform()!='win-amd64':
        raise ValueError('This offline calculation bundle requires Windows x64 (including x64 emulation).')
    directory=Path(directory);root=Path(root);data=manifest(directory)
    if data.get('environment_version')!=ENV_VERSION or backend not in data['backends']:
        raise ValueError('This offline bundle does not contain the selected environment version.')
    def check():
        if cancelled():raise InterruptedError('Offline setup cancelled. Run setup again to continue.')
    check();emit('Preparing the bundled CPU environment. No network downloads are used.')
    uv=verified_file(directory,data,'uv.exe')
    lock=verified_file(directory,data,f'{backend}.txt')
    archive=verified_file(directory,data,'python.zip');check()
    runtime=root/('offline-python-'+data['files']['python.zip'][:12])
    root.mkdir(parents=True,exist_ok=True)
    if not (runtime/'python.exe').is_file():
        with tempfile.TemporaryDirectory(prefix='offline-python-',dir=root) as temp:
            extract_python(archive,temp,cancelled);check()
            if not (Path(temp)/'python.exe').is_file():raise ValueError('Offline Python runtime is missing.')
            Path(temp).rename(runtime)
    process_env=external_environment()
    process_env.update(UV_OFFLINE='1',UV_PYTHON_DOWNLOADS='never',UV_NO_CONFIG='1',
        UV_CACHE_DIR=str(root/'package-cache'),PYTHONNOUSERSITE='1')
    def command(args):
        check();emit(' '.join(map(str,args)))
        with tempfile.TemporaryFile() as log:
            with external_libraries():
                process=subprocess.Popen(list(map(str,args)),stdout=log,stderr=subprocess.STDOUT,
                    env=process_env,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                while True:
                    check()
                    try:code=process.wait(timeout=.2);break
                    except subprocess.TimeoutExpired:pass
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=30)
                log.seek(0);emit(log.read().decode('utf-8','replace'))
            if code:raise RuntimeError('Offline environment installation failed. See the setup log; no online fallback was attempted.')
    python=managed_python(root,backend) if target is None else Path(target);env=python.parent.parent
    # uv writes pyvenv.cfg and scripts at the final path; a copied venv would
    # retain the build machine's absolute interpreter/entry-point paths.
    if not python.is_file():command([uv,'venv','--offline','--no-config','--no-python-downloads','--python',runtime/'python.exe',env])
    command([uv,'pip','sync','--offline','--no-config','--no-index','--no-build','--require-hashes',
        '--find-links',directory/'wheels','--python',python,lock])
    check();shutil.copyfile(lock,env/'installed-lock.txt')
    (env/'offline-bundle.json').write_text(json.dumps({'format':1,'backend':backend,'lock_sha256':data['files'][f'{backend}.txt']}),encoding='utf-8')
    return str(python)
