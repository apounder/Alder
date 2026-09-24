"""Run the same MLIP checks used by the packaged executable."""
import json,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from alder.mlip_smoke import run
with tempfile.TemporaryDirectory() as folder:
    report=Path(folder)/'report.json'
    code=run(report,os.environ.get('MLIP_TEST_PYTHON'),os.environ.get('MLIP_TEST_CACHE'))
    print(report.read_text(),flush=True)
    sys.exit(code)
