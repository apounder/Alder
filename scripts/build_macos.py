"""Build a native Mac app, check the installed copy, and produce DMG and ZIP."""
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import tomllib

from release_files import write_notices

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = 'Alder.app'


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def verify_app(app, architecture):
    with (app / 'Contents' / 'Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    if info['CFBundleIdentifier'] != 'org.alder.desktop':
        raise RuntimeError('Unexpected app bundle identifier.')
    run('/usr/bin/lipo', '-verify_arch', architecture, app / 'Contents' / 'MacOS' / info['CFBundleExecutable'])
    run('/usr/bin/codesign', '--verify', '--deep', '--strict', app)


def main():
    if sys.platform != 'darwin' or platform.machine() not in ('arm64', 'x86_64'):
        raise SystemExit('Build on a Mac, or run the macOS download workflow on GitHub.')
    if int(platform.mac_ver()[0].split('.')[0]) < 15:
        raise SystemExit('The initial macOS builds require macOS 15 or newer.')
    architecture = platform.machine()
    label = 'AppleSilicon' if architecture == 'arm64' else 'Intel'
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    release = ROOT / 'dist' / 'release'
    release.mkdir(parents=True, exist_ok=True)
    stem = f'Alder-{version}-macOS-{label}'
    notes = ROOT / 'build' / 'macos-notices'
    if notes.exists():
        shutil.rmtree(notes)
    write_notices(notes, version)
    shutil.copy2(ROOT / 'packaging' / 'START-HERE-macOS.txt', notes / 'START-HERE.txt')
    env = os.environ.copy()
    env['PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR'] = '1'
    env['PYINSTALLER_VERIFY_BUNDLE_SIGNATURE'] = '1'
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        ROOT / 'packaging' / 'Alder.spec', cwd=ROOT, env=env)
    app = ROOT / 'dist' / APP_NAME
    verify_app(app, architecture)

    # ditto preserves .app framework symlinks, resource forks, and permissions.
    archive = release / f'{stem}.zip'
    archive.unlink(missing_ok=True)
    run('/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', app, archive)
    dmg = release / f'{stem}.dmg'
    report = ROOT / 'build' / f'macos-{label}-smoke.json'
    report.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='Alder é ') as temporary:
        folder = Path(temporary)
        stage = folder / 'disk-image'
        stage.mkdir()
        run('/usr/bin/ditto', app, stage / APP_NAME)
        (stage / 'Applications').symlink_to('/Applications', target_is_directory=True)
        shutil.copy2(notes / 'START-HERE.txt', stage / 'START-HERE.txt')
        run('/usr/bin/hdiutil', 'create', '-volname', 'Alder', '-srcfolder', stage,
            '-format', 'UDZO', '-ov', dmg)
        run('/usr/bin/hdiutil', 'verify', dmg)
        mount = folder / 'mounted'
        mount.mkdir()
        run('/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', mount, dmg)
        try:
            # Equivalent to dragging from the DMG into a writable Applications folder.
            installed = folder / 'Applications' / APP_NAME
            run('/usr/bin/ditto', mount / APP_NAME, installed)
            verify_app(installed, architecture)
        finally:
            run('/usr/bin/hdiutil', 'detach', mount)
        for key in ('PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH'):
            env.pop(key, None)
        env['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
        launch_environment = []
        for key in ('PATH', 'QTWEBENGINE_CHROMIUM_FLAGS', 'QSG_RHI_BACKEND', 'PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH'):
            launch_environment.extend(('--env', f'{key}={env.get(key, "")}'))
        # Use LaunchServices, as Finder does. The report also catches an app that
        # exits unsuccessfully even if `open` itself returned success.
        run('/usr/bin/open', '-n', '-W', '-a', installed, *launch_environment, '--args', '--smoke-test', report,
            ROOT / 'tests' / 'data', cwd=folder, env=env, timeout=300)
        result = json.loads(report.read_text(encoding='utf-8'))
        if not result.get('ok') or not result.get('frozen'):
            raise RuntimeError(f'Installed app check failed; see {report}')
        extracted = folder / 'zip-check'
        run('/usr/bin/ditto', '-x', '-k', archive, extracted)
        verify_app(extracted / APP_NAME, architecture)
    checksums = []
    for path in (dmg, archive):
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        checksums.append(f'{digest}  {path.name}')
    (release / f'{stem}-SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
    print(f'macOS {label} test downloads are ready in {release}. Not Apple-notarized.')


if __name__ == '__main__':
    main()
