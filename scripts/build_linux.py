"""Build a native Linux desktop package and portable archive; verify the frozen app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib

from release_files import write_notices

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = ('libc6 (>= 2.39), libegl1, libopengl0, libnss3, libnspr4, '
                'libxcb-cursor0, libxkbcommon-x11-0, libasound2t64, libx11-6, '
                'libxcomposite1, libxdamage1, libxrandr2, libxtst6, libxss1, '
                'libgbm1, libdrm2, libfontconfig1, libglib2.0-0t64, libdbus-1-3')


def package_deb(bundle, output, version, architecture):
    with tempfile.TemporaryDirectory(prefix='alder-deb-') as temporary:
        stage = Path(temporary)
        stage.chmod(0o755)
        shutil.copytree(bundle, stage / 'opt/alder', symlinks=True)
        desktop = stage / 'usr/share/applications/org.alder.Desktop.desktop'
        desktop.parent.mkdir(parents=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Alder\n'
            'Comment=Molecular viewer, figures, and local model setup\n'
            'Exec=/opt/alder/Alder\nIcon=alder\nTerminal=false\n'
            'Categories=Education;Science;Chemistry;\n', encoding='utf-8')
        icons = stage / 'usr/share/icons/hicolor/scalable/apps'
        icons.mkdir(parents=True)
        shutil.copy2(ROOT / 'src/alder/assets/alder.svg', icons / 'alder.svg')
        binary = stage / 'usr/bin/alder'
        binary.parent.mkdir(parents=True)
        binary.symlink_to('/opt/alder/Alder')
        control = stage / 'DEBIAN/control'
        control.parent.mkdir()
        size = sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file()) // 1024
        control.write_text(f'Package: alder\nVersion: {version}\nArchitecture: {architecture}\n'
            'Maintainer: Alder maintainers <noreply@github.com>\nSection: science\nPriority: optional\n'
            f'Installed-Size: {size}\nDepends: {DEPENDENCIES}\n'
            'Homepage: https://github.com/apounder/alder\n'
            'Description: Molecular viewer, editor, and local MLIP desktop\n'
            ' Includes graphical model setup. Model downloads are optional.\n', encoding='utf-8')
        # A bundle copied from a Windows volume can report every file as 0777.
        for path in stage.rglob('*'):
            if not path.is_symlink():
                path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(output)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if sys.platform != 'linux' or platform.machine() not in ('x86_64', 'aarch64'):
        raise SystemExit('Build on Linux x86_64/arm64, or use the Linux download workflow.')
    if not shutil.which('dpkg-deb'):
        raise SystemExit('Install dpkg-dev before building the Linux package.')
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    label, architecture = ('x64', 'amd64') if platform.machine() == 'x86_64' else ('arm64', 'arm64')
    dist = args.dist_dir.resolve()
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                    '--distpath', str(dist), str(ROOT / 'packaging/Alder.spec')], cwd=ROOT, check=True)
    bundle = dist / 'Alder'
    shutil.copy2(ROOT / 'packaging/START-HERE-Linux.txt', bundle / 'START-HERE.txt')
    write_notices(bundle, version)
    report = ROOT / 'build' / f'linux-{label}-smoke.json'
    report.unlink(missing_ok=True)
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH'):
        env.pop(key, None)
    env['PATH'] = '/usr/bin:/bin'
    # Test relocation, Unicode/spaces, and execution without the build Python on PATH.
    with tempfile.TemporaryDirectory(prefix='Alder é ') as folder:
        installed = Path(folder) / 'Alder'
        shutil.copytree(bundle, installed, symlinks=True)
        env['ALDER_MLIP_HOME'] = str(Path(folder) / 'model-data')
        env['XDG_STATE_HOME'] = str(Path(folder) / 'state')
        env['XDG_CACHE_HOME'] = str(Path(folder) / 'cache')
        env['XDG_CONFIG_HOME'] = str(Path(folder) / 'config')
        try:
            subprocess.run([str(installed / 'Alder'), '--smoke-test', str(report), str(ROOT / 'tests/data')],
                           cwd=folder, env=env, check=True, timeout=600)
        except subprocess.SubprocessError:
            log = Path(env['XDG_STATE_HOME']) / 'Alder/studio.log'
            if log.exists():
                print(log.read_text(encoding='utf-8'), file=sys.stderr)
            raise
    result = json.loads(report.read_text(encoding='utf-8'))
    if not result.get('ok') or not result.get('frozen'):
        raise RuntimeError(f'Frozen Linux app check failed: {report}')
    release = dist / 'release'
    release.mkdir(parents=True, exist_ok=True)
    stem = f'Alder-{version}-Linux-{label}'
    deb = release / (stem + '.deb')
    package_deb(bundle, deb, version, architecture)
    archive = Path(shutil.make_archive(str(release / stem), 'gztar', root_dir=dist, base_dir='Alder'))
    lines = []
    for path in (deb, archive):
        with path.open('rb') as stream:
            lines.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}')
    (release / (stem + '-SHA256SUMS.txt')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Linux downloads ready: {release}')


if __name__ == '__main__':
    main()
