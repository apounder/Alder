"""Interactive terminal installation, model checks, and CPU/CUDA repair."""
import argparse
import getpass
import shlex
from pathlib import Path
import subprocess
import sys

from .mlip.environment import choose_device, hardware, redact
from .mlip.registry import CATALOGUE
from .mlip.setup import (ACCESS_URL, TOKEN_URL, cached, data_root, licensed,
                         read_json, run_setup, select_models, setup_lock)


def ask(question, default):
    return input(f'{question} [{default}]: ').strip() or default


def print_catalogue():
    for index, (name, spec) in enumerate(CATALOGUE.items(), 1):
        access = 'Hugging Face approval' if spec['backend'] == 'uma' else 'licence acknowledgement' if licensed(name) else 'public; no account'
        print(f'  {index}. {name} ({access})')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', help='recommended, all, none, backend names, or comma-separated checkpoint names')
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], help='auto detects this computer; cuda requires a working NVIDIA GPU')
    parser.add_argument('--repair', action='store_true', help='build and test a replacement environment; preserve weights and jobs')
    parser.add_argument('--check', action='store_true', help='check existing environments and weights without downloading')
    parser.add_argument('--list', action='store_true', help='list model choices and exit')
    parser.add_argument('--non-interactive', action='store_true', help='never prompt; use saved credentials or HF_TOKEN')
    parser.add_argument('--accept-license', action='append', default=[], metavar='CHECKPOINT', help='acknowledge this checkpoint’s published licence (repeat for each)')
    parser.add_argument('--launch', action='store_true', help='open the desktop after successful setup')
    args = parser.parse_args(argv)
    if args.list:
        print_catalogue()
        return 0
    if args.repair and args.check:
        parser.error('Choose --repair or --check, not both.')
    interactive = sys.stdin.isatty() and not args.non_interactive
    if not interactive and args.models is None and not args.check and not args.repair:
        parser.error('No interactive terminal. Supply --models and --device, or run this command in a terminal.')
    try:
        root = data_root()
        print('Alder — models and hardware setup\n')
        info = hardware()
        print(f'Processor: {info["cpu"]} ({info["threads"]} logical cores)')
        for gpu in info['gpus']:
            print(f'NVIDIA GPU: {gpu["name"]}, {gpu["memory_mb"]} MB, driver {gpu["driver"]}')
        print(info.get('error') or info.get('note') or 'An NVIDIA GPU is available for a CUDA installation check.')
        print(f'Models and calculation environments: {root}\n')
        with setup_lock(root):
            state = read_json(root / 'setup-state.json')
            previous = ','.join(state.get('selection', [])) or 'recommended'
            if args.check or args.repair:
                existing = read_json(root / 'environments.json')
                installed = [c.get('last_ready_model', {}).get('checkpoint') for c in existing.values()]
                if not state.get('selection') and any(installed):
                    previous = ','.join(n for n in installed if n in CATALOGUE)
            if args.models is None and interactive:
                print_catalogue()
                print('\nChoose numbers separated by commas, recommended, all, or none for the viewer only.')
                names = select_models(ask('Models to set up', previous))
            else:
                names = select_models(args.models or previous)
            requested = args.device or (state.get('device', 'auto') if args.check else 'auto')
            if args.device is None and interactive and names:
                requested = ask('Calculation device: auto, cpu, or cuda', requested).lower()
            device = choose_device(requested, info) if names else 'cpu'
            accepted = list(args.accept_license)
            needs_auth = []
            for name in names:
                if args.check or cached(root, name, repair=args.repair):
                    continue
                spec = CATALOGUE[name]
                if licensed(name) and state.get('licences', {}).get(name) != spec['license'] and name not in accepted:
                    print(f'\n{name}: {spec["license"]}')
                    if interactive and ask('Do you have the required access and accept these terms? yes/no', 'no').lower() in ('y', 'yes'):
                        accepted.append(name)
                if spec['backend'] == 'uma':
                    needs_auth.append(name)
            token = None
            if needs_auth and interactive:
                from huggingface_hub import get_token
                print(f'\nUMA access: {ACCESS_URL}\nCreate a read token: {TOKEN_URL}')
                use_saved = bool(get_token()) and ask('Use your existing Hugging Face login? yes/no', 'yes').lower() in ('y', 'yes')
                if not use_saved:
                    token = getpass.getpass('Hugging Face read token (hidden; Enter to defer UMA): ').strip() or None
            if names:
                print(f'\nSelected: {", ".join(names)}\nDevice: {device.upper()}')
                print('Allow several GB of disk space per calculator. GPU packages can require additional downloads.')
            if interactive and ask('Check installation?' if args.check else 'Continue with setup? yes/no', 'yes').lower() not in ('y', 'yes'):
                return 130
            success = run_setup(root, names, device, accepted=accepted, token=token,
                                repair=args.repair, check_only=args.check)
            token = None
        python = "& '" + sys.executable.replace("'", "''") + "'" if sys.platform == 'win32' else shlex.quote(sys.executable)
        command = python + ' -m alder'
        print('\nReopen this walkthrough with:\n  ' + command + ' setup')
        if success:
            print('Start the app with:\n  ' + command)
            launch = args.launch or (interactive and ask('Open Alder now? yes/no', 'yes').lower() in ('y', 'yes'))
            if launch:
                subprocess.Popen([sys.executable, '-m', 'alder'])
        return 0 if success else 1
    except (KeyboardInterrupt, EOFError, InterruptedError):
        print('\nSetup stopped. Run the same command again to continue completed steps.')
        return 130
    except Exception as error:
        print('\nSetup needs attention: ' + redact(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
