"""Recreate all three offline environments at a fresh path; deny worker networking."""
import argparse
import json
import os
from pathlib import Path
import shutil
from contextlib import contextmanager
import subprocess
import sys
import tempfile
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from molecule_studio.mlip.environment import managed_environment
from molecule_studio.mlip.offline import manifest


@contextmanager
def temporary_workspace():
    folder=tempfile.mkdtemp(prefix='Studio offline é ')
    try:yield folder
    finally:
        # PyTorch's nested licence paths exceed MAX_PATH on otherwise supported
        # Windows systems; Rust/uv installs them, so Python must remove them too.
        shutil.rmtree(('\\\\?\\'+folder) if sys.platform=='win32' else folder)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();bundle=args.bundle.resolve();report={'ok':False,'checks':[],'models':{}}
    os.environ.update(MOLECULE_STUDIO_OFFLINE_BUNDLE=str(bundle),HF_HUB_OFFLINE='1',UV_OFFLINE='1',
                      HTTP_PROXY='http://127.0.0.1:9',HTTPS_PROXY='http://127.0.0.1:9')
    worker=Path(__file__).resolve().parents[1]/'src/molecule_studio/mlip/worker.py'
    try:
        with temporary_workspace() as folder:
            root=Path(folder);block=root/'deny-network';block.mkdir()
            (block/'sitecustomize.py').write_text("import sys\ndef audit(event,args):\n if event=='socket.connect':raise RuntimeError('Offline validation: network connection forbidden')\nsys.addaudithook(audit)\n",encoding='utf-8')
            env=os.environ|{'PYTHONPATH':str(block),'PYTHONNOUSERSITE':'1','PATH':os.environ['SystemRoot']+'\\System32'}
            def run(python,action,*options):
                output=root/'result.json';output.unlink(missing_ok=True)
                p=subprocess.run([python,str(worker),action,*map(str,options),'--result',str(output)],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
                assert p.returncode==0,p.stdout+'\n'+p.stderr
                return json.loads(output.read_text())
            for backend in ('aimnet2','mace','uma'):
                python=managed_environment(root,backend)
                value=run(python,'probe','--backend',backend)
                assert value['ready'] and value['sella'] and value['devices']==['cpu'],value
                report['checks'].append(backend+': relocated Python, locked CPU dependencies and Sella import with networking denied')
                for model in manifest(bundle)['models']:
                    if model['backend']!=backend:continue
                    config=root/'config.json';config.write_text(json.dumps({'backend':backend,'checkpoint':model['name'],'device':'cpu','precision':'float32'}))
                    run(python,'download','--config',config,'--cache',root/'models','--bundled-cache',bundle/'models')
                    value=run(python,'check','--config',config,'--cache',root/'models')
                    assert value['ready'] and value['sha256']==model['sha256'],value
                    report['models'][model['name']]={'sha256':value['sha256'],'energy_eV':value['energy'],'max_force_eV_A':value['max_force']}
                assert managed_environment(root,backend)==python
            report['checks'].append('Repeated local setup reuses all three installed environments')
            assert not (root/'models/uma').exists()
            report['checks'].append('Gated/licensed weights and credentials excluded')
        report['ok']=True
    except Exception:report['error']=traceback.format_exc()
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
