"""Launchers preserve environments; releases contain verified native downloads."""
import hashlib
import json
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
from alder import desktop

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_linux import package_deb
from prepare_release import collect


@pytest.mark.skipif(not shutil.which('gio'), reason='Linux desktop launcher required')
def test_linux_launcher_preserves_venv_and_literal_paths(tmp_path, monkeypatch):
    python = tmp_path / 'Alder é $cash `literal` 100% "quoted"' / 'bin/python'
    python.parent.mkdir(parents=True)
    # Resolving this symlink would lose the venv and its installed app.
    output = tmp_path / 'arguments.txt'
    helper = tmp_path / 'record-arguments'
    helper.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > ' + shlex.quote(str(output)) + '\n')
    helper.chmod(0o755)
    python.symlink_to(helper)
    monkeypatch.setattr(desktop, 'sys', SimpleNamespace(platform='linux', executable=str(python)))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    entry, = desktop.install_shortcuts()
    fields = dict(line.split('=', 1) for line in entry.read_text().splitlines() if '=' in line)
    assert 'bin/python' in fields['Exec'] and 'record-arguments' not in fields['Exec']
    subprocess.run(['gio', 'launch', str(entry)], check=True)
    deadline = time.monotonic() + 5
    while not output.exists() and time.monotonic() < deadline:
        time.sleep(.02)
    assert output.read_text().splitlines() == ['-m', 'alder']
    assert fields['Terminal'] == 'false'
    assert entry == desktop.install_shortcuts()[0]


def test_macos_bundle_forwards_arguments_and_retains_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    python = tmp_path / "venv with space and 'quote" / 'bin/python'
    python.parent.mkdir(parents=True)
    monkeypatch.setattr(desktop, 'sys', SimpleNamespace(platform='darwin', executable=str(python)))
    app, = desktop.install_shortcuts()
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    launcher = app / 'Contents/MacOS' / info['CFBundleExecutable']
    assert (app / 'Contents/Resources/alder.icns').is_file()
    assert shlex.quote(str(python)) in launcher.read_text()
    if sys.platform != 'win32':
        assert launcher.stat().st_mode & 0o111
        python.write_text('#!/bin/sh\nprintf "%s\\n" "$ALDER_DESKTOP_LAUNCH" "$@"\n')
        python.chmod(0o755)
        result = subprocess.run([str(launcher), '--smoke-test', 'file with spaces'],
                                check=True, text=True, capture_output=True)
        assert result.stdout.splitlines() == ['1', '-m', 'alder', '--smoke-test', 'file with spaces']


def test_windows_shortcut_passes_paths_as_data(tmp_path, monkeypatch):
    python = tmp_path / 'pythonw.exe'
    python.touch()
    monkeypatch.setattr(desktop, 'sys', SimpleNamespace(platform='win32', executable=str(tmp_path / 'python.exe')))
    def run(command, **options):
        data = json.loads(options['input'])
        assert data['python'] == str(python)
        assert str(python) not in command[-1]
        assert "$link.Arguments = '-m alder'" in command[-1]
        assert options['encoding'] == 'utf-8'
        return SimpleNamespace(stdout=json.dumps([str(tmp_path / 'Alder Source.lnk')]))
    monkeypatch.setattr(desktop.subprocess, 'run', run)
    assert desktop.install_shortcuts() == [tmp_path / 'Alder Source.lnk']


def test_frozen_app_does_not_create_source_shortcuts(monkeypatch):
    monkeypatch.setattr(desktop, 'sys', SimpleNamespace(frozen=True))
    assert desktop.install_shortcuts() == []


@pytest.mark.skipif(not shutil.which('dpkg-deb'), reason='Debian packaging tool required')
def test_deb_contains_executable_and_application_menu(tmp_path):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'Alder').write_text('#!/bin/sh\nexit 0\n')
    (bundle / 'Alder').chmod(0o777)
    output = tmp_path / 'Alder.deb'
    package_deb(bundle, output, '0.4.0', 'arm64')
    listing = subprocess.run(['dpkg-deb', '--contents', str(output)],
                             check=True, text=True, capture_output=True).stdout
    assert listing.splitlines()[0].split()[:2] == ['drwxr-xr-x', 'root/root']
    installed = tmp_path / 'installed'
    subprocess.run(['dpkg-deb', '-x', str(output), str(installed)], check=True)
    assert (installed / 'opt/alder/Alder').stat().st_mode & 0o777 == 0o755
    entry = installed / 'usr/share/applications/org.alder.Desktop.desktop'
    assert 'Exec=/opt/alder/Alder' in entry.read_text()
    assert (installed / 'usr/share/icons/hicolor/scalable/apps/alder.svg').is_file()


@pytest.mark.parametrize('problem', [None, 'missing', 'corrupt', 'incomplete'])
def test_release_requires_windows_downloads_and_valid_checksums(tmp_path, problem):
    source = tmp_path / 'downloads'
    source.mkdir()
    names = [f'Alder-0.4.0-{suffix}' for suffix in ('Windows-x64-GUI-Setup.exe',
        'Windows-x64-GUI-Portable.zip')]
    digest = hashlib.sha256(b'fixture').hexdigest()
    for name in names:
        (source / name).write_bytes(b'fixture')
    (source / 'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n' for name in names))
    if problem == 'missing':
        (source / names[-1]).unlink()
    if problem == 'corrupt':
        (source / names[0]).write_bytes(b'changed after validation')
    if problem == 'incomplete':
        (source / 'SHA256SUMS.txt').write_text(f'{digest}  {names[0]}\n')
    output = tmp_path / 'release'
    if problem:
        with pytest.raises(ValueError):
            collect(source, output, '0.4.0')
        assert not output.exists()
    else:
        assert sorted(collect(source, output, '0.4.0')) == sorted(names)
        assert len(list(output.iterdir())) == 3
