"""External Python entry point. Never invoked using the frozen GUI executable."""
if __package__ in (None,''):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    __package__='mlip'

import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
from .environment import atomic_json, availability, download, probe, redact


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['run','probe','download','login','check','availability'])
    parser.add_argument('--db');parser.add_argument('--job');parser.add_argument('--cache');parser.add_argument('--workdir');parser.add_argument('--bundled-cache')
    parser.add_argument('--parent-pid',type=int);parser.add_argument('--backend');parser.add_argument('--config');parser.add_argument('--structure');parser.add_argument('--result');parser.add_argument('--licensed',action='store_true')
    args=parser.parse_args()
    try:
        if args.action=='login':
            from huggingface_hub import login
            token=sys.stdin.readline().strip()
            if not token:raise ValueError('A Hugging Face read token is required; create one using the link in setup.')
            login(token=token,add_to_git_credential=False)
            token=None
            result={'connected':True}
        elif args.action=='probe':result=probe(args.backend)
        elif args.action in ('download','check','availability'):
            config=json.loads(Path(args.config).read_text())
            if args.action=='availability':result=availability(config,args.cache)
            elif args.action=='download':result=download(config,args.cache,args.licensed,args.bundled_cache)
            else:
                from .adapters import create
                from .contract import snapshot, atoms_from_input
                from .registry import model_path
                from ase import Atoms
                structure=dict(numbers=[8,1,1],positions=[[0,0,0],[.96,0,0],[-.24,.93,0]],charge=0,multiplicity=1)
                if args.structure:structure=json.loads(Path(args.structure).read_text())
                data=snapshot(structure,config,'sp')
                calc,provenance=create(data,args.cache)
                a=atoms_from_input(data);a.calc=calc
                energy=float(a.get_potential_energy());forces=a.get_forces()
                import numpy as np
                if not np.isfinite(energy) or not np.isfinite(forces).all():raise ValueError('Model readiness calculation returned nonfinite values.')
                result=dict(ready=True,sha256=provenance['model']['sha256'],provenance=provenance,energy=energy,max_force=float(np.linalg.norm(forces,axis=1).max()))
        else:
            from .adapters import create
            from .engine import Context, run, Cancelled
            from .store import Store
            store=Store(args.db)
            if not store.claim(args.job):return 2
            store.artifact(args.job,'worker',{'pid':os.getpid(),'parent_pid':args.parent_pid})
            try:
                data=store.job(args.job)['input']
                store.event(args.job,'Loading explicitly selected checkpoint in the worker process.')
                calc,provenance=create(data,args.cache);store.artifact(args.job,'provenance',provenance)
                ctx=Context(store,args.job,calc,args.workdir);ctx.parent_pid=args.parent_pid
                status=run(ctx);store.state(args.job,status)
            except Cancelled:
                store.state(args.job,'cancelled');store.event(args.job,'Cancelled; saved frames/checkpoint retained.')
            except InterruptedError as error:
                store.state(args.job,'interrupted',str(error))
            except Exception as error:
                detail=('Out of memory. Reduce the system size or use a larger device. ' if isinstance(error,MemoryError) or 'out of memory' in str(error).lower() else '')+redact(error)
                store.event(args.job,detail);store.state(args.job,'failed',detail)
                return 1
            finally:store.close()
            return 0
        if args.result:atomic_json(args.result,result)
        else:print(json.dumps(result))
        return 0
    except Exception as error:
        message=redact(error)
        if args.result:atomic_json(args.result,{'error':message,'ready':False})
        print(message,file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
