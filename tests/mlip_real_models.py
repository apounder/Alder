"""Opt-in real-checkpoint acceptance runner. JSON outcomes are evidence, never mocks."""
import argparse,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import numpy as np
from ase import Atoms
from ase.build import molecule
from molecule_studio.mlip.contract import snapshot
from molecule_studio.mlip.adapters import create
from molecule_studio.mlip.engine import Context, run, frequencies
from molecule_studio.mlip.store import Store


def numerical_checks(ctx):
 a=ctx.atoms;p=a.positions.copy();force=a.get_forces().copy();difference=np.zeros_like(force);original=ctx.opts
 try:
  for i in range(len(a)):
   for axis in range(3):
    plus=p.copy();plus[i,axis]+=.001;a.positions[:]=plus;ep=a.get_potential_energy()
    minus=p.copy();minus[i,axis]-=.001;a.positions[:]=minus;em=a.get_potential_energy()
    difference[i,axis]=-(ep-em)/.002
  a.positions[:]=p
  result=dict(force_consistency=dict(error_eV_per_A=float(np.max(np.abs(force-difference))),tolerance=.002,components=int(force.size)))
  assert result['force_consistency']['error_eV_per_A']<.002,result
  if hasattr(ctx.calc.base,'get_hessian'):
   ctx.opts=original|{'hessian':'analytical'};analytical=frequencies(ctx,save=False)
   ctx.opts=original|{'hessian':'finite_difference','displacement':.01,'nfree':2};finite=frequencies(ctx,save=False)
   delta=float(np.max(np.abs(np.array(analytical['frequencies'])-finite['frequencies'])))
   result['hessian_consistency']=dict(max_frequency_difference_cm1=delta,tolerance_cm1=5.)
   assert delta<5.,result
  return result
 finally:a.positions[:]=p;ctx.opts=original


def main():
 p=argparse.ArgumentParser();p.add_argument('--backend',choices=['mace','aimnet2','uma'],required=True);p.add_argument('--cache',required=True);p.add_argument('--output',required=True);p.add_argument('--numerics-only',action='store_true');args=p.parse_args()
 name={'mace':'MACE-ANI-CC','aimnet2':'aimnet2-wb97m-d3_0','uma':'uma-s-1p2'}[args.backend]
 config=dict(backend=args.backend,checkpoint=name,device='cpu',precision='float64' if args.backend=='mace' else 'float32',task='omol' if args.backend=='uma' else None,head=None,domain_ack=True,corrections='checkpoint')
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True);store=Store(out/'jobs.sqlite');results={}
 water=dict(name='water',numbers=[8,1,1],positions=[[0,0,0],[.96,0,0],[-.24,.93,0]],charge=0,multiplicity=1)
 calc,provenance=create(snapshot(water,config,'sp'),args.cache)
 def execute(label,kind,s=water,settings=None,constraints=None):
  t=time.monotonic();data=snapshot(s,config,kind,settings,constraints);ident=store.submit(data);assert store.claim(ident)
  try:
   c=Context(store,ident,calc,out);state=run(c);store.state(ident,state);results[label]=dict(state=state,job=ident,seconds=time.monotonic()-t,frames=store.count(ident))
   print(label,results[label],flush=True);(out/'results.json').write_text(json.dumps(dict(backend=args.backend,provenance=provenance,results=results),indent=2))
   return c
  except Exception as e:
   store.state(ident,'failed',str(e));results[label]=dict(state='failed',error=str(e),seconds=time.monotonic()-t);traceback.print_exc();(out/'results.json').write_text(json.dumps(dict(backend=args.backend,results=results),indent=2));return None
 c=execute('single_point','sp')
 if c:results.update(numerical_checks(c))
 if args.numerics_only:
  assert c is not None
  (out/'results.json').write_text(json.dumps(dict(backend=args.backend,provenance=provenance,results=results),indent=2));print(results,flush=True);return
 for optimizer in ['BFGS','LBFGS','FIRE']:execute('opt_'+optimizer,'opt',settings=dict(optimizer=optimizer,steps=150,fmax=.015))
 c=execute('optimization_frequencies','optfreq',settings=dict(steps=150,fmax=.01))
 if c:
  child=store.artifact(c.id,'workflow')['child'];assert store.claim(child);fc=Context(store,child,calc,out)
  try:state=run(fc);store.state(child,state);results['optimization_frequencies']['state']=store.job(c.id)['status'];results['frequencies']=store.artifact(child,'frequencies')['frequencies']
  except Exception as e:store.state(child,'failed',str(e));results['frequencies']={'error':str(e)}
 execute('constrained','constrained',settings=dict(fmax=.015,steps=150),constraints=[dict(kind='bond',atoms=[0,1],value=1.0)])
 for axes in [[dict(kind='bond',atoms=[0,1],start=.95,stop=1.05,points=3)],
              [dict(kind='bond',atoms=[0,1],start=.95,stop=1.0,points=2),dict(kind='angle',atoms=[1,0,2],start=100.,stop=110.,points=2)]]:
  execute('scan_'+str(len(axes))+'d','scan',settings=dict(scans=axes,steps=150,fmax=.015))
 ammonia=molecule('NH3');nh=dict(name='ammonia',numbers=ammonia.numbers.tolist(),positions=ammonia.positions.tolist(),charge=0,multiplicity=1)
 nh_ts=json.loads(json.dumps(nh));nh_ts['positions']=(ammonia.positions*np.array([1,1,0])).tolist()
 ts=execute('transition_state','ts',nh_ts,dict(steps=150,fmax=.015,sella_internal=False))
 if ts:
  saddle=store.artifact(ts.id,'saddle');results['saddle_verification']=saddle
  if saddle['verified_first_order_saddle']:
   guess=nh_ts|{'positions':ts.atoms.positions.tolist()}
   execute('irc_both','irc',guess,dict(steps=100,fmax=.03,irc_dx=.08,endpoint_opt=False))
 product=nh|{'positions':(np.asarray(nh['positions'])*np.array([1,1,-1])).tolist()}
 execute('climbing_neb','neb',nh,dict(product=product,mapping=list(range(4)),images=5,interpolation='idpp',climb=True,optimizer='FIRE',steps=150,fmax=.04))
 for ensemble in ['nve','nvt']:execute('md_'+ensemble,'md',settings=dict(ensemble=ensemble,steps=30,stride=5,timestep=.2,temperature=100))
 from rdkit import Chem
 from rdkit.Chem import AllChem
 mol=Chem.AddHs(Chem.MolFromSmiles('CC'));AllChem.EmbedMolecule(mol,randomSeed=42)
 ethane=dict(name='ethane',numbers=[a.GetAtomicNum() for a in mol.GetAtoms()],positions=mol.GetConformer().GetPositions().tolist(),charge=0,multiplicity=1,
  bonds=[dict(a=b.GetBeginAtomIdx(),b=b.GetEndAtomIdx(),order=b.GetBondTypeAsDouble()) for b in mol.GetBonds()])
 c=execute('conformer_search','conformers',ethane,dict(candidates=3,steps=150,fmax=.03))
 if c:results['conformers_retained']=store.artifact(c.id,'conformers')['retained']
 (out/'results.json').write_text(json.dumps(dict(backend=args.backend,provenance=provenance,results=results),indent=2))
 required=['single_point','opt_BFGS','opt_LBFGS','opt_FIRE','optimization_frequencies','constrained','scan_1d','scan_2d','transition_state','irc_both','climbing_neb','md_nve','md_nvt','conformer_search']
 assert all(results.get(k,{}).get('state')=='completed' for k in required), results
 assert results['force_consistency']['error_eV_per_A']<results['force_consistency']['tolerance']
 assert results['saddle_verification']['verified_first_order_saddle']
 assert results['conformers_retained']
if __name__=='__main__':main()
