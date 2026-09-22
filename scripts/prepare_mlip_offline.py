"""Build the Windows x64 offline kit from validated, separately managed backends.

Maintainer-only online step. End users install exclusively from local wheels.
No Hugging Face credentials or restricted checkpoints are copied into the kit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from molecule_studio.mlip.environment import ENV_VERSION, PYTHON_VERSION, managed_environment, managed_python
from molecule_studio.mlip.registry import CATALOGUE, checksum, model_path

PUBLIC_MODELS=['MACE-ANI-CC','aimnet2-wb97m-d3_0','aimnet2-b973c-2025-d3_0','aimnet2-nse_0','aimnet2-rxn_0']


def run(args,**kw):
    print(' '.join(map(str,args)),flush=True)
    return subprocess.run(list(map(str,args)),check=True,**kw)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment-root',type=Path,default=ROOT/'.build-tools/mlip-source')
    parser.add_argument('--output',type=Path,default=ROOT/'.build-tools/mlip-offline')
    args=parser.parse_args();out=args.output.resolve();source=args.environment_root.resolve()
    if sys.platform!='win32' or sysconfig.get_platform()!='win-amd64':raise SystemExit('Prepare this kit on Windows x64 Python.')
    if os.environ.get('MOLECULE_STUDIO_OFFLINE_BUNDLE'):raise SystemExit('Unset MOLECULE_STUDIO_OFFLINE_BUNDLE for the online preparation step.')
    out.mkdir(parents=True,exist_ok=True);(out/'manifest.json').unlink(missing_ok=True)
    for cached in (out/'models').glob('*/*'):
        if cached.name not in PUBLIC_MODELS:raise ValueError('Offline kit contains a non-public or unlisted checkpoint; use a clean output directory.')
    wheels=out/'wheels';wheels.mkdir(exist_ok=True)
    worker=ROOT/'src/molecule_studio/mlip/worker.py';versions={};used_wheels=set()
    notices=out/'ThirdPartyLicenses'
    if notices.exists():shutil.rmtree(notices)
    notices.mkdir()
    for backend in ('aimnet2','mace','uma'):
        python=managed_python(source,backend)
        if not python.is_file():python=Path(managed_environment(source,backend))
        report=out/f'{backend}-probe.json'
        run([python,worker,'probe','--backend',backend,'--result',report])
        value=json.loads(report.read_text())
        if not value.get('ready') or not value.get('sella') or value.get('devices')!=['cpu']:
            raise RuntimeError(f'{backend} must pass the CPU-only calculator and Sella probes: {value}')
        versions[backend]=value['versions'];report.unlink()
        lock=run([source/'tools/uv.exe','pip','freeze','--python',python],capture_output=True,text=True).stdout
        if any(not re.fullmatch(r'[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+',line) for line in lock.splitlines() if line):
            raise ValueError('Only pinned public package versions may enter the offline kit; no editable/local/URL requirements.')
        raw=out/f'{backend}.txt';raw.write_text(lock,encoding='utf-8')
        # Build/download wheels with the calculation interpreter (3.12), even
        # when the GUI builder uses 3.14. Small source-only packages are compiled
        # here; end users receive wheels and never need a compiler.
        def matching_wheels(line):
            name,version=line.split('==');normal=re.sub(r'[-_.]+','_',name).lower()
            return [p for p in wheels.glob('*.whl') if p.name.split('-')[0].lower()==normal and p.name.split('-')[1]==version]
        if any(not matching_wheels(line) for line in lock.splitlines() if line):
            run([sys.executable,'-m','pip','--python',python,'wheel','--no-deps',
                 '--prefer-binary','--find-links',wheels,'--wheel-dir',wheels,'-r',raw])
        hashed=[]
        for line in lock.splitlines():
            if not line:continue
            candidates=matching_wheels(line)
            if not candidates:raise ValueError(f'Missing wheel for {line}')
            hashed.append(line+' '+' '.join('--hash=sha256:'+checksum(p) for p in candidates));used_wheels.update(p.name for p in candidates)
        raw.write_text('\n'.join(hashed)+'\n',encoding='utf-8')
    for path in wheels.glob('*.whl'):
        if path.name not in used_wheels:path.unlink()
    # Package one relocatable standalone base, never an existing venv.
    python=managed_python(source,'aimnet2')
    base=Path(run([python,'-c','import sys; print(sys.base_prefix)'],capture_output=True,text=True).stdout.strip())
    with zipfile.ZipFile(out/'python.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(base.rglob('*')):
            relative=path.relative_to(base)
            if path.is_file() and '__pycache__' not in relative.parts and path.suffix!='.pyc' and 'site-packages' not in relative.parts:
                z.write(path,relative.as_posix())
    shutil.copy2(base/'LICENSE.txt',notices/'Python-LICENSE.txt')
    shutil.copy2(source/'tools/uv.exe',out/'uv.exe')
    # ZIPs preserve all nested notices without Windows MAX_PATH truncation.
    for wheel in wheels.glob('*.whl'):
        with zipfile.ZipFile(wheel) as z, zipfile.ZipFile(notices/(wheel.stem+'.zip'),'w',zipfile.ZIP_DEFLATED) as licenses:
            for name in z.namelist():
                if '.dist-info/' in name and (Path(name).name=='METADATA' or any(k in name.lower() for k in ('license','notice','copying','author'))) and not name.endswith('/'):
                    licenses.writestr(name,z.read(name))
    # uv is bootstrapped from an official wheel, whose licences ship in this kit too.
    uvmeta=out/'uv-wheel';uvmeta.mkdir(exist_ok=True)
    from molecule_studio.mlip.environment import UV_VERSION
    run([sys.executable,'-m','pip','download','--no-deps','--only-binary=:all:',f'uv=={UV_VERSION}','--dest',uvmeta])
    for wheel in uvmeta.glob('*.whl'):
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if any(k in name.lower() for k in ('license','notice','copying')) and not name.endswith('/'):
                    target=notices/'uv'/Path(name).name;target.parent.mkdir(exist_ok=True);target.write_bytes(z.read(name))
    shutil.rmtree(uvmeta)
    config=out/'model-config.json';models=[]
    try:
        for name in PUBLIC_MODELS:
            spec=CATALOGUE[name];backend=spec['backend'];cfg={'checkpoint':name,'backend':backend}
            config.write_text(json.dumps(cfg),encoding='utf-8')
            # Reuse verified public cache files; download only explicit public names.
            try:
                path,_=model_path(cfg,source/'models')
                target=out/'models'/backend/name/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            except FileNotFoundError:pass
            run([managed_python(source,backend),worker,'download','--config',config,'--cache',out/'models'])
            _,verified=model_path(cfg,out/'models');models.append({k:verified[k] for k in ('name','backend','sha256','url')})
    finally:config.unlink(missing_ok=True)
    # Checkpoint software licences are retained from the MACE/AIMNet2 wheels above.
    files={name:checksum(out/name) for name in ('uv.exe','python.zip','aimnet2.txt','mace.txt','uma.txt')}
    data={'format':1,'platform':'win-amd64','environment_version':ENV_VERSION,'python':PYTHON_VERSION,
          'backends':versions,'models':models,'files':files}
    (out/'manifest.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    (out/'README.txt').write_text('Windows x64 CPU calculation kit. Local installation only: Python, uv, locked wheels and five public checkpoints.\n'
        'UMA / MACE-OFF23 weights and credentials are not included. Licences are in ThirdPartyLicenses and inside each wheel.\n'
        'This directory contains no jobs, user configuration or Hugging Face login. Keep the complete directory beside MoleculeStudio.exe.\n',encoding='utf-8')
    print(f'Offline kit prepared: {out}',flush=True)


if __name__=='__main__':main()
