"""Opt-in real CPU/CUDA install check; always uses an explicit isolated root."""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from molecule_studio.mlip.environment import hardware, choose_device
from molecule_studio.mlip.setup import run_setup, select_models, setup_lock
from molecule_studio.mlip.registry import model_path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', required=True, type=Path)
parser.add_argument('--device', required=True, choices=['cpu', 'cuda'])
parser.add_argument('--models', default='aimnet2-wb97m-d3_0')
parser.add_argument('--cache', type=Path, help='Reuse verified public weights from an existing cache')
args = parser.parse_args()
names = select_models(args.models)
root = args.root.resolve()
root.mkdir(parents=True, exist_ok=True)
print(json.dumps(hardware(), indent=2), flush=True)
choose_device(args.device)
if args.cache:
    for name in names:
        try:
            source, spec = model_path({'checkpoint': name}, args.cache)
        except FileNotFoundError:
            continue
        target = root / 'models' / spec['backend'] / name / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists(): shutil.copy2(source, target)
        receipt = source.with_suffix(source.suffix + '.json')
        if receipt.exists(): shutil.copy2(receipt, target.with_suffix(target.suffix + '.json'))
with setup_lock(root):
    passed = run_setup(root, names, args.device, emit=lambda s: print(s, flush=True))
raise SystemExit(0 if passed else 1)
