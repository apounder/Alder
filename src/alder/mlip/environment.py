"""Explicit model downloads, reproducible environment recipe, and readiness probes."""
import importlib.metadata
import csv
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import urllib.request
import zipfile
from contextlib import contextmanager
from threading import RLock
from .registry import CATALOGUE, checksum, model_path, specification

ENV_VERSION='1'
PYTHON_VERSION='3.12.14'
UV_VERSION='0.12.17'
COMMON=['ase==3.29.0','numpy==2.4.3','scipy==1.17.1','rdkit==2026.3.6','huggingface-hub==0.36.0']
PACKAGES={'mace':['torch==2.13.0','mace-torch==0.3.16'],
          'aimnet2':['torch==2.13.0','aimnet[ase]==0.2.0'],
          'uma':['torch==2.13.0','fairchem-core==2.22.0']}
_launch_lock=RLock()


def external_environment():
    """Restore OS libraries for independent Python/uv processes in a frozen GUI."""
    env=os.environ.copy();env.update(PYTHONUNBUFFERED='1',PYTHONUTF8='1')
    if getattr(sys,'frozen',False):
        for key in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH'):
            original=env.get(key+'_ORIG')
            if original:env[key]=original
            else:env.pop(key,None)
        for key in ('PYTHONHOME','PYTHONPATH','QT_PLUGIN_PATH','QML2_IMPORT_PATH'):env.pop(key,None)
        bundle=os.path.normcase(os.path.abspath(sys._MEIPASS))
        env['PATH']=os.pathsep.join(p for p in env.get('PATH','').split(os.pathsep)
            if p and not (os.path.normcase(os.path.abspath(p))==bundle or
                          os.path.normcase(os.path.abspath(p)).startswith(bundle+os.sep)))
    return env


@contextmanager
def external_libraries():
    # SetDllDirectory is process-wide: serialize only process creation, not execution.
    with _launch_lock:
        frozen_windows=getattr(sys,'frozen',False) and sys.platform=='win32'
        if frozen_windows:
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:yield
        finally:
            if frozen_windows:ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)


def redact(text):
    text=re.sub(r'hf_[A-Za-z0-9]+','[redacted]',(str(text) or type(text).__name__) if isinstance(text,BaseException) else str(text))
    text=re.sub(r'(https?://[^\s?]+)\?[^\s]+',r'\1?[redacted-query]',text)
    return re.sub(r'(?i)(authorization|token|password)([=: ]+)[^\s,;]+',r'\1\2[redacted]',text)


def atomic_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf-8');os.replace(temp,p)


def download(config,cache,allow_licensed=False,bundled_cache=None):
    spec=specification(config)
    if config.get('local_file'):
        path,spec=model_path(config,cache);return dict(path=str(path),sha256=spec['sha256'])
    directory=Path(cache)/spec['backend']/spec['name'];directory.mkdir(parents=True,exist_ok=True)
    path=directory/('weights'+Path(spec.get('file',spec.get('url','model.pt'))).suffix)
    try:
        p,found=model_path(config,cache);return dict(path=str(p),sha256=found['sha256'])
    except (FileNotFoundError,ValueError):pass
    if spec['backend']=='uma' or spec['name'].startswith('MACE-OFF23'):
        if not allow_licensed:raise ValueError('This checkpoint requires access/licence acknowledgement in Model setup before download.')
    temp=path.with_suffix(path.suffix+'.part')
    try:
        if bundled_cache and spec['backend']!='uma' and not spec['name'].startswith('MACE-OFF23'):
            source,_=model_path(config,bundled_cache)
            shutil.copyfile(source,temp)
        elif spec['backend']=='uma':
            from huggingface_hub import hf_hub_download
            source=hf_hub_download(repo_id=spec['repo'],filename=spec['file'],revision=spec['revision'],cache_dir=str(Path(cache)/'huggingface'))
            shutil.copyfile(source,temp)
        else:
            with urllib.request.urlopen(spec['url'],timeout=60) as response,temp.open('wb') as out:
                shutil.copyfileobj(response,out,1024*1024)
        value=checksum(temp)
        if spec.get('sha256') and value!=spec['sha256']:raise ValueError('Downloaded checkpoint checksum mismatch.')
        os.replace(temp,path);atomic_json(path.with_suffix(path.suffix+'.json'),dict(sha256=value,specification=spec))
        return dict(path=str(path),sha256=value)
    finally:temp.unlink(missing_ok=True)


def availability(config,cache):
    """Inspect local weights/login without a network request or returning secrets."""
    spec=specification(config)
    try:
        path,found=model_path(config,cache)
        return dict(cached=True,sha256=found['sha256'])
    except FileNotFoundError:
        if config.get('local_file'):raise
    # A corrupt file is an error, not permission to silently replace it.
    result=dict(cached=False,licensed=spec['backend']=='uma' or spec['name'].startswith('MACE-OFF23'))
    if spec['backend']=='uma':
        from huggingface_hub import get_token
        result['authenticated']=bool(get_token())
    return result


def hardware():
    """Inspect this host without importing Torch or depending on an MLIP environment."""
    result=dict(cpu=platform.processor() or platform.machine(),threads=os.cpu_count() or 1,
                platform=platform.system(),architecture=platform.machine(),gpus=[],error='')
    if sys.platform=='darwin':
        result['note']='CUDA requires an NVIDIA GPU on Windows or Linux. Use CPU on macOS.'
        return result
    executable=shutil.which('nvidia-smi')
    if not executable:
        candidates=[Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/nvidia-smi.exe',
                    Path(os.environ.get('ProgramW6432',os.environ.get('ProgramFiles','C:/Program Files')))/'NVIDIA Corporation/NVSMI/nvidia-smi.exe',
                    Path('/usr/lib/wsl/lib/nvidia-smi')]
        executable=next((str(p) for p in candidates if p.is_file()),None)
    if not executable:
        result['note']='NVIDIA driver tools were not found. CPU is available; install an NVIDIA driver and recheck to enable CUDA.'
        return result
    try:
        with external_libraries():
            run=subprocess.run([executable,'--query-gpu=index,name,driver_version,memory.total,uuid',
                                '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15,
                               env=external_environment(),creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        if run.returncode:raise RuntimeError((run.stderr or run.stdout).strip() or 'NVIDIA driver query failed.')
        for row in csv.reader(run.stdout.splitlines()):
            if len(row)!=5:raise ValueError('Unexpected NVIDIA driver response.')
            index,name,driver,memory,ident=(v.strip() for v in row)
            result['gpus'].append(dict(index=int(index),name=name,driver=driver,memory_mb=memory,uuid=ident))
        if not result['gpus']:result['note']='The NVIDIA driver reported no available GPUs.'
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        result['error']='Could not check NVIDIA hardware: '+redact(error)
    return result


def choose_device(requested,info=None):
    if requested not in ('auto','cpu','cuda'):raise ValueError('Choose auto, cpu, or cuda.')
    if requested=='cpu':return 'cpu'
    info=hardware() if info is None else info
    if info.get('error'):raise ValueError(info['error']+' Recheck the driver, or choose CPU explicitly.')
    if info['gpus']:return 'cuda'
    if requested=='cuda':raise ValueError(info.get('note','No NVIDIA GPU was detected.')+' GPU driver help: https://www.nvidia.com/Download/index.aspx')
    return 'cpu'


def managed_python(root,backend,device='cpu'):
    if backend not in PACKAGES:raise ValueError('Unknown calculator backend.')
    if device not in ('cpu','cuda'):raise ValueError('Unknown calculation device.')
    suffix='-cuda' if device=='cuda' else ''
    return Path(root)/f'env-v{ENV_VERSION}-{backend}{suffix}'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')


def probe(backend):
    import importlib
    result=dict(protocol=1,python=sys.version,executable=sys.executable,backend=backend,devices=[],versions={},errors=[])
    packages={'mace':'mace.calculators','aimnet2':'aimnet.calculators','uma':'fairchem.core'}
    try:
        import torch
        importlib.import_module(packages[backend]);result['devices']=['cpu']
        result.update(torch_build=torch.__version__,torch_cuda=torch.version.cuda)
        if torch.cuda.is_available():
            try:
                x=torch.ones(2,device='cuda');float((x*x).sum().cpu());torch.cuda.synchronize();result['devices'].append('cuda')
                result['gpu']=torch.cuda.get_device_name()
            except Exception as error:result['errors'].append('CUDA probe failed: '+redact(error))
        else:
            result['cuda_error']=('This environment has CPU-only PyTorch. Use Guided setup → GPU to install CUDA support.'
                if torch.version.cuda is None else 'CUDA packages are installed, but the NVIDIA driver/device is unavailable. Update the driver and recheck, or choose CPU.')
    except Exception as error:result['errors'].append(redact(error))
    for module in ('ase','numpy','scipy','torch','sella','rdkit','mace-torch','aimnet','fairchem-core'):
        try:result['versions'][module]=importlib.metadata.version(module)
        except importlib.metadata.PackageNotFoundError:pass
    try:
        from sella import Sella, IRC
        result['sella']=True
    except Exception as error:
        result['sella']=False;result['errors'].append('TS/IRC unavailable: '+redact(error))
    expected={'mace':('mace-torch','0.3.16'),'aimnet2':('aimnet','0.2.0'),'uma':('fairchem-core','2.22.0')}[backend]
    if result['versions'].get(expected[0])!=expected[1]:
        result['errors'].append(f'Expected {expected[0]}=={expected[1]}.');result['devices']=[]
    for name,version in [('ase','3.29.0'),('torch','2.13.0')]:
        if result['versions'].get(name,'').split('+')[0]!=version:
            result['errors'].append(f'Expected {name}=={version}; use the managed recipe or a matching environment.');result['devices']=[]
    if result['versions'].get('sella')!='2.6.0':
        result['sella']=False;result['errors'].append('TS/IRC require Sella 2.6.0 with this ASE version.')
    result['ready']=bool(result['devices'])
    return result


def ensure_uv(root,emit=print):
    """Download the pinned, digest-verified installer for this Python's architecture."""
    tools=Path(root)/'tools';tools.mkdir(parents=True,exist_ok=True)
    windows=sys.platform=='win32';machine=platform.machine().lower()
    if windows:machine='arm64' if sysconfig.get_platform()=='win-arm64' else 'amd64'
    tag=('win_arm64' if machine in ('arm64','aarch64') else 'win_amd64') if windows else (
        'macosx_11_0_arm64' if machine in ('arm64','aarch64') else 'macosx_10_12_x86_64') if sys.platform=='darwin' else (
        'manylinux_2_28_aarch64' if machine in ('arm64','aarch64') else 'manylinux_2_28_x86_64')
    uv=tools/('uv.exe' if windows else 'uv')
    if not uv.exists():
        emit(f'Downloading verified uv {UV_VERSION} installer…')
        with urllib.request.urlopen(f'https://pypi.org/pypi/uv/{UV_VERSION}/json',timeout=30) as response:metadata=json.load(response)
        item=next((f for f in metadata['urls'] if f['filename'].endswith(tag+'.whl')),None)
        if item is None:raise RuntimeError(f'No managed installer for {platform.system()} {machine}.')
        wheel=tools/'uv.whl'
        with urllib.request.urlopen(item['url'],timeout=60) as response,wheel.open('wb') as out:shutil.copyfileobj(response,out)
        if checksum(wheel)!=item['digests']['sha256']:raise ValueError('Installer checksum failed.')
        with zipfile.ZipFile(wheel) as archive:
            member=next(n for n in archive.namelist() if n.endswith('/'+uv.name))
            temporary=uv.with_suffix('.part')
            temporary.write_bytes(archive.read(member));temporary.chmod(0o755)
            os.replace(temporary,uv)
        wheel.unlink()
    return uv


def managed_environment(root,backend,emit=print,cancelled=lambda:False,*,device='cpu',target=None):
    """Called by a setup thread, never by a calculation. uv owns downloads/venvs."""
    from .offline import bundle_directory, install_environment
    bundle=bundle_directory()
    if bundle is not None and device=='cpu':
        if target is None:return install_environment(bundle,root,backend,emit,cancelled)
        return install_environment(bundle,root,backend,emit,cancelled,target=target)
    if device not in ('cpu','cuda'):raise ValueError('Choose CPU or CUDA before installing.')
    if device=='cuda':choose_device('cuda')
    root=Path(root);python=managed_python(root,backend,device) if target is None else Path(target);env=python.parent.parent
    def check_cancelled():
        if cancelled():raise InterruptedError('Setup stopped; completed downloads and installation steps are retained. Run setup again to continue.')
    check_cancelled()
    windows=sys.platform=='win32';uv=ensure_uv(root,emit)
    process_env=external_environment()
    process_env.update(UV_PYTHON_INSTALL_DIR=str(root/'python'),UV_CACHE_DIR=str(root/'package-cache'))
    def command(args,required=True):
        check_cancelled()
        emit(' '.join(map(str,args)))
        flags=subprocess.CREATE_NO_WINDOW if windows else 0
        with external_libraries():
            process=subprocess.Popen(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=flags,env=process_env)
        with process:
            for line in process.stdout:emit(redact(line.rstrip()))
            code=process.wait()
        check_cancelled()
        if code and required:
            remedy=('Update your NVIDIA driver and retry Guided setup, or select CPU.' if device=='cuda' else
                    'Check your connection and free disk space, then rerun Guided setup.')
            raise RuntimeError('Environment setup failed; see the setup log. '+remedy)
        return code
    if not python.exists():command([uv,'venv','--managed-python','--python',PYTHON_VERSION,env])
    # uv chooses the official CUDA wheel index from this host's driver. CPU is
    # explicit, including on Linux where PyPI's default Torch can include CUDA.
    runtime=['--torch-backend','auto' if device=='cuda' else 'cpu']
    command([uv,'pip','install','--python',python,*runtime,*COMMON,*PACKAGES[backend]])
    sella_code=command([uv,'pip','install','--python',python,*runtime,'sella==2.6.0'],required=False)
    if sella_code:emit('Sella build failed. TS/IRC require a compatible C/C++ compiler or a preconfigured environment; other jobs can be checked independently.')
    with external_libraries():
        process=subprocess.Popen([str(uv),'pip','freeze','--python',str(python)],stdout=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW if windows else 0,env=process_env)
    with process:
        lock=process.communicate()[0]
        if process.returncode:raise RuntimeError('Could not record the installed environment lock.')
    (env/'installed-lock.txt').write_text(lock,encoding='utf-8')
    return str(python)


def process_alive(pid):
    if not isinstance(pid,int) or pid<=0:return False
    if sys.platform=='win32':
        import ctypes
        api=ctypes.windll.kernel32
        api.OpenProcess.restype=ctypes.c_void_p
        handle=api.OpenProcess(0x100000,False,pid)
        if not handle:return False
        try:return api.WaitForSingleObject(ctypes.c_void_p(handle),0)==258
        finally:api.CloseHandle(ctypes.c_void_p(handle))
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False
    except PermissionError:return True
