"""Build and smoke-check a Windows x64 bundle, then make the installer and ZIP."""
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

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != 'win32' or sysconfig.get_platform() != 'win-amd64':
        raise SystemExit('Build on 64-bit Windows, or run the Windows download workflow on GitHub.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist-dir', type=Path, default=ROOT/'dist', help='Output directory; use a separate directory while an older portable copy is running.')
    dist = parser.parse_args().dist_dir.resolve()
    compiler = shutil.which('ISCC.exe') or str(Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe')
    if not Path(compiler).is_file():
        raise SystemExit('Install Inno Setup 6.3+ first. GitHub Windows runners already include it.')
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                    '--distpath', str(dist), str(ROOT / 'packaging' / 'MoleculeStudio.spec')], cwd=ROOT, check=True)
    bundle = dist / 'MoleculeStudio'
    shutil.copy2(ROOT / 'packaging' / 'START-HERE.txt', bundle)
    write_notices(bundle, version)

    report = ROOT / 'build' / 'portable-smoke.json'
    # Strip Python/developer paths and run away from the checkout. The bundle
    # must supply its own interpreter, DLLs, JavaScript, WASM, and Qt resources.
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH'):
        env.pop(key, None)
    env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
    with tempfile.TemporaryDirectory(prefix='Molecule Studio é ') as cwd:
        subprocess.run([str(bundle / 'MoleculeStudio.exe'), '--smoke-test', str(report),
                        str(ROOT / 'tests' / 'data')], cwd=cwd, env=env, check=True, timeout=300)
    result = json.loads(report.read_text(encoding='utf-8'))
    if not result.get('ok') or not result.get('frozen'):
        raise SystemExit(f'Packaged application check failed; see {report}')

    release = dist / 'release'
    release.mkdir(parents=True, exist_ok=True)
    subprocess.run([compiler, f'/DAppVersion={version}', f'/DBundleDir={bundle}', f'/O{release}', str(ROOT / 'packaging' / 'windows.iss')], check=True)
    stem = f'MoleculeStudio-{version}-Windows-x64'
    portable = Path(shutil.make_archive(str(release / f'{stem}-Portable'), 'zip', root_dir=bundle.parent, base_dir=bundle.name))
    installer = release / f'{stem}-Setup.exe'
    lines = []
    for path in (installer, portable):
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        lines.append(f'{checksum}  {path.name}')
    (release / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Windows downloads are ready in {release}')


if __name__ == '__main__':
    main()
