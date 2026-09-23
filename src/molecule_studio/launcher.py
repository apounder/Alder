"""Desktop entry point, including diagnostics for packaged desktop apps."""
from datetime import datetime
import multiprocessing
import os
from pathlib import Path
import sys
import traceback


def main():
    multiprocessing.freeze_support()
    smoke = sys.argv[1:2] in (['--smoke-test'], ['--mlip-smoke-test'])
    log_path = None
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('MoleculeStudio.Desktop')
        if sys.stderr is None:
            log_path = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Molecule Studio' / 'studio.log'
    elif sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        log_path = Path.home() / 'Library' / 'Logs' / 'Molecule Studio' / 'studio.log'
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists() and log_path.stat().st_size > 2_000_000:
            log_path.replace(log_path.with_suffix('.previous.log'))
        sys.stderr = log_path.open('a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stderr
        print(f'\nMolecule Studio started {datetime.now().isoformat()}', file=sys.stderr)
    try:
        if sys.argv[1:2] == ['--setup']:
            from .setup_ui import standalone
            return standalone()
        if sys.argv[1:2] == ['--mlip-smoke-test']:
            from .mlip_smoke import run
            return run(Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv)>3 else None, Path(sys.argv[4]) if len(sys.argv)>4 else None)
        if smoke:
            from .smoke import run
            return run(Path(sys.argv[2]), Path(sys.argv[3]))
        from .app import main as run_app
        return run_app()
    except Exception:
        details = traceback.format_exc()
        print(details, file=sys.stderr)
        if smoke and len(sys.argv) > 2:
            import json
            Path(sys.argv[2]).write_text(json.dumps({'ok': False, 'error': details}), encoding='utf-8')
        elif sys.platform == 'win32':
            message = 'Molecule Studio could not start.\n\n' + (
                f'Diagnostic details were saved to:\n{log_path}' if log_path else details)
            ctypes.windll.user32.MessageBoxW(None, message, 'Molecule Studio', 0x10)
        return 1
