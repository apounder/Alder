"""Dependency notices shared by the Windows and macOS release builders."""
from importlib.metadata import distributions
from pathlib import Path
import platform
import shutil
import sys


def write_notices(destination, version):
    destination.mkdir(parents=True, exist_ok=True)
    licenses = destination / 'ThirdPartyLicenses'
    licenses.mkdir(exist_ok=True)
    installed = list(distributions())
    for dist in installed:
        for file in dist.files or []:
            if '.dist-info/' not in file.as_posix():
                continue
            if file.name != 'METADATA' and not any(word in file.as_posix().lower() for word in ('license', 'copying', 'notice', 'author')):
                continue
            source = Path(dist.locate_file(file))
            if source.is_file():
                target = licenses / file
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    for python_license in (Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'Resources' / 'English.lproj' / 'License.rtf'):
        if python_license.is_file():
            shutil.copy2(python_license, licenses / ('Python-' + python_license.name))
    freeze = '\n'.join(sorted(f"{dist.metadata['Name']}=={dist.version}" for dist in installed))
    (destination / 'build-info.txt').write_text(f'Alder {version}\nPython {sys.version}\n{platform.platform()}\n\n{freeze}', encoding='utf-8')
