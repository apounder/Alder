"""Build Windows GUI and optional MLIP Offline installers/portable ZIPs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import tomllib
from release_files import write_notices

ROOT=Path(__file__).resolve().parents[1]


def main():
    if sys.platform!='win32' or sysconfig.get_platform()!='win-amd64':
        raise SystemExit('Build on 64-bit Windows, or run the Windows download workflow on GitHub.')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist-dir',type=Path,default=ROOT/'dist')
    parser.add_argument('--offline-kit',type=Path,help='Prepared kit from scripts/prepare_mlip_offline.py; builds both editions.')
    args=parser.parse_args();dist=args.dist_dir.resolve()
    compiler=shutil.which('ISCC.exe') or str(Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Inno Setup 6/ISCC.exe')
    if not Path(compiler).is_file():raise SystemExit('Install Inno Setup 6.3+ first. GitHub Windows runners include it.')
    if args.offline_kit and not (args.offline_kit/'manifest.json').is_file():raise SystemExit('Prepare a complete offline kit first.')
    version=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--distpath',str(dist),str(ROOT/'packaging/MoleculeStudio.spec')],cwd=ROOT,check=True)
    bundle=dist/'MoleculeStudio';shutil.copy2(ROOT/'packaging/START-HERE.txt',bundle);write_notices(bundle,version)
    env=os.environ.copy()
    for key in ('PYTHONPATH','PYTHONHOME','QT_PLUGIN_PATH','QML2_IMPORT_PATH','MOLECULE_STUDIO_OFFLINE_BUNDLE'):env.pop(key,None)
    env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
    def smoke(folder,mlip=False):
        report=ROOT/'build'/('offline-desktop-smoke.json' if mlip else 'portable-smoke.json')
        options=['--mlip-smoke-test',str(report)] if mlip else ['--smoke-test',str(report),str(ROOT/'tests/data')]
        check_env=env.copy()
        if mlip:check_env.update(UV_OFFLINE='1',HF_HUB_OFFLINE='1',HTTP_PROXY='http://127.0.0.1:9',HTTPS_PROXY='http://127.0.0.1:9')
        with tempfile.TemporaryDirectory(prefix='Molecule Studio é ') as cwd:
            subprocess.run([str(folder/'MoleculeStudio.exe'),*options],cwd=cwd,env=check_env,check=True,timeout=1800 if mlip else 300)
        result=json.loads(report.read_text(encoding='utf-8'))
        if not result.get('ok') or not result.get('frozen'):raise SystemExit(f'Packaged app check failed; see {report}')
    smoke(bundle)
    editions=[('GUI',bundle)]
    if args.offline_kit:
        offline=dist/'MoleculeStudio-MLIP-Offline'
        if offline.exists():shutil.rmtree(offline)
        shutil.copytree(bundle,offline);shutil.copytree(args.offline_kit,offline/'mlip-offline')
        smoke(offline,True);editions.append(('MLIP-Offline',offline))
    write_downloads(editions,version,dist,compiler)


def write_downloads(editions,version,dist,compiler):
    release=dist/'release';release.mkdir(parents=True,exist_ok=True);assets=[]
    for edition,folder in editions:
        subprocess.run([compiler,f'/DAppVersion={version}',f'/DEdition={edition}',f'/DBundleDir={folder}',f'/O{release}',str(ROOT/'packaging/windows.iss')],check=True)
        stem=f'MoleculeStudio-{version}-Windows-x64-{edition}'
        portable=Path(shutil.make_archive(str(release/f'{stem}-Portable'),'zip',root_dir=folder.parent,base_dir=folder.name))
        assets.extend([release/f'{stem}-Setup.exe',portable])
    # Keep only these successfully built downloads in the generated release folder.
    # Source/history and installed applications are never touched by this cleanup.
    for path in release.iterdir():
        if path.is_file() and path not in assets and (path.name.startswith('MoleculeStudio-') and path.suffix in ('.zip','.exe') or path.name=='SHA256SUMS.txt'):path.unlink()
    lines=[]
    for path in assets:
        with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        lines.append(f'{digest}  {path.name}')
    (release/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Windows downloads are ready in {release}')


if __name__=='__main__':main()
