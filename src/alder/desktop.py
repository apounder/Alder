"""Native launchers for an installed Python/Conda copy of Alder."""
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys


def desktop_command(arguments):
    """Quote Exec arguments through both desktop-entry and command parsing."""
    quoted = []
    for argument in arguments:
        value = str(argument).replace('%', '%%')
        value = ''.join('\\' + c if c in '\\"`$' else c for c in value)
        quoted.append('"' + value.replace('\\', '\\\\') + '"')
    return ' '.join(quoted)


def install_shortcuts():
    """Return the launcher paths; packaged installers manage their own entries."""
    if getattr(sys, 'frozen', False):
        return []
    python = Path(sys.executable).absolute()  # Preserve the venv path, not its symlink target.
    assets = Path(__file__).parent / 'assets'
    home = Path.home()
    if sys.platform == 'win32':
        python = python.with_name('pythonw.exe')
        if not python.is_file():
            raise FileNotFoundError(f'Windowed Python is missing: {python}')
        script = '''
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$config = [Console]::In.ReadToEnd() | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$paths = @()
foreach ($folder in @('Programs', 'Desktop')) {
    $directory = [Environment]::GetFolderPath($folder)
    if (-not $directory) { continue }
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $path = Join-Path $directory 'Alder Source.lnk'
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $config.python
    $link.Arguments = '-m alder'
    $link.WorkingDirectory = $config.home
    $link.IconLocation = $config.icon
    $link.Description = 'Open Alder and manage local models'
    $link.Save()
    $paths += $path
}
ConvertTo-Json -InputObject @($paths) -Compress
'''
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
            input=json.dumps(dict(python=str(python), home=str(home), icon=str(assets / 'alder.ico'))),
            capture_output=True, text=True, encoding='utf-8', check=True)
        return [Path(path) for path in json.loads(result.stdout)]
    if sys.platform == 'darwin':
        app = home / 'Applications' / 'Alder Source.app'
        contents = app / 'Contents'
        (contents / 'MacOS').mkdir(parents=True, exist_ok=True)
        (contents / 'Resources').mkdir(exist_ok=True)
        launcher = contents / 'MacOS' / 'Alder'
        launcher.write_text('#!/bin/sh\nexport ALDER_DESKTOP_LAUNCH=1\nexec ' +
                            shlex.quote(str(python)) + ' -m alder "$@"\n', encoding='utf-8')
        launcher.chmod(0o755)
        shutil.copy2(assets / 'alder.icns', contents / 'Resources' / 'alder.icns')
        with (contents / 'Info.plist').open('wb') as stream:
            plistlib.dump(dict(CFBundleExecutable='Alder', CFBundleName='Alder Source',
                CFBundleIdentifier='org.alder.source', CFBundlePackageType='APPL',
                CFBundleIconFile='alder.icns', NSHighResolutionCapable=True), stream)
        return [app]
    if sys.platform.startswith('linux'):
        directory = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share') / 'applications'
        directory.mkdir(parents=True, exist_ok=True)
        entry = directory / 'org.alder.Source.desktop'
        entry.write_text('[Desktop Entry]\nType=Application\nName=Alder Source\n'
            'Comment=Molecular viewer, figures, and local model setup\n'
            'Exec=' + desktop_command(['/usr/bin/env', 'ALDER_DESKTOP_LAUNCH=1', python, '-m', 'alder']) + '\n'
            'Icon=' + str(assets / 'alder.svg') + '\nTerminal=false\nCategories=Education;Science;Chemistry;\n',
            encoding='utf-8')
        return [entry]
    raise OSError(f'Desktop launchers are not supported on {sys.platform}')
