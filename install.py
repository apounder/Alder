"""Install this checkout into .venv and walk through model/hardware setup."""
import argparse
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog='Other options are passed to molecule-studio-setup; for example --models all --device auto.')
    parser.add_argument('--environment', type=Path, default=Path('.venv'), help='app environment directory (default: .venv)')
    args, setup_args = parser.parse_known_args()
    root = Path(__file__).resolve().parent
    if sys.version_info < (3, 11):
        raise SystemExit('Use Python 3.11 or newer to start setup, or follow the Conda instructions in README.md.')
    if not shutil.which('git'):
        raise SystemExit('Git is needed to install the pinned cclib parser. Install Git from https://git-scm.com/downloads, reopen your terminal, and retry; or use the Conda instructions, which install Git automatically.')
    sys.path.insert(0, str(root / 'src'))
    from molecule_studio.mlip.environment import ensure_uv, redact
    environment = args.environment.resolve()
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    other_python = environment / ('bin/python' if sys.platform == 'win32' else 'Scripts/python.exe')
    if other_python.exists():
        raise SystemExit('This environment belongs to another operating system. Use --environment .venv-local to create a separate one.')
    try:
        uv = ensure_uv(root / '.build-tools')
        process_env = os.environ | {'UV_CACHE_DIR': str(root / '.build-tools/package-cache'),
                                   'UV_PYTHON_INSTALL_DIR': str(root / '.build-tools/python')}
        if not python.is_file():
            subprocess.run([str(uv), 'venv', '--managed-python', '--python', '3.14', str(environment)], env=process_env, check=True)
        print('Installing Molecule Studio and its desktop dependencies…', flush=True)
        subprocess.run([str(uv), 'pip', 'install', '--python', str(python),
                        '--reinstall-package', 'molecule-studio', str(root)], env=process_env, check=True)
        command = "& '" + str(python).replace("'", "''") + "'" if sys.platform == 'win32' else shlex.quote(str(python))
        print(f'\nLater, launch the app with:\n  {command} -m molecule_studio\n', flush=True)
        return subprocess.call([str(python), '-m', 'molecule_studio', 'setup', *setup_args])
    except KeyboardInterrupt:
        print('\nInstallation stopped. Rerun python install.py to continue.')
        return 130
    except Exception as error:
        print('Installation failed: ' + redact(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
