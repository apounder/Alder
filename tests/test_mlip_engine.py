import json
import numpy as np
import pytest
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes
from alder.mlip.contract import snapshot, coordinate, wrap_angle, validate_constraints
from alder.mlip.engine import Context, run, Cancelled, frequencies, rmsd
from alder.mlip.store import Store

class PairPotential(Calculator):
    implemented_properties=['energy','forces']
    def __init__(self,double=False,**kw):super().__init__(**kw);self.double=double
    def calculate(self,atoms=None,properties=('energy','forces'),system_changes=all_changes):
        super().calculate(atoms,properties,system_changes)
        p=atoms.positions;d=p[1]-p[0];r=np.linalg.norm(d);u=d/r
        e=(r-1)**2*(r-2)**2 if self.double else 0.5*5*(r-1)**2
        grad=2*(r-1)*(r-2)*(2*r-3) if self.double else 5*(r-1)
        f=np.zeros_like(p);f[0]=grad*u;f[1]=-grad*u
        self.results={'energy':e,'forces':f}


def context(tmp_path,kind,settings=None,r=1.1,double=False,constraints=None):
    s=dict(numbers=[1,1],positions=[[0,0,0],[r,0,0]],charge=0,multiplicity=1)
    data=snapshot(s,{},kind,settings,constraints)
    store=Store(tmp_path/'jobs.sqlite');ident=store.submit(data);assert store.claim(ident)
    return Context(store,ident,PairPotential(double),tmp_path)


def test_contract_and_signed_torsion():
    p=[[-2,0,0],[0,0,0],[0,2,0],[0,2,2]]
    a=Atoms('CCCC',positions=p)
    assert coordinate(p,[0,1,2,3])==90
    assert wrap_angle(a.get_dihedral(0,1,2,3))==90
    assert wrap_angle(181)==-179
    with pytest.raises(ValueError,match='conflict'):
        validate_constraints([{'kind':'freeze','atoms':[0,1]},{'kind':'bond','atoms':[0,1],'value':1}],np.array(p))
    with pytest.raises(ValueError,match='Collinear'):
        coordinate([[0,0,0],[1,0,0],[2,0,0],[3,0,0]],[0,1,2,3])


def test_sp_units_and_order(tmp_path):
    c=context(tmp_path,'sp');assert run(c)=='completed'
    f=c.store.get_frame(c.id,0)
    assert f['energy']==pytest.approx(.025)
    np.testing.assert_allclose(f['forces'],[[.5,0,0],[-.5,0,0]],atol=1e-12)
    assert f['positions']==c.data['structure']['positions']

@pytest.mark.parametrize('optimizer',['BFGS','LBFGS','FIRE'])
def test_optimization(tmp_path,optimizer):
    c=context(tmp_path,'opt',{'optimizer':optimizer,'fmax':1e-5,'steps':500});assert run(c)=='completed'
    assert np.linalg.norm(c.atoms.positions[0]-c.atoms.positions[1])==pytest.approx(1,abs=3e-6)


def test_limit_cancel_and_store(tmp_path):
    c=context(tmp_path,'opt',{'steps':1,'fmax':1e-10},r=2)
    assert run(c)=='unconverged'
    c.store.cancel(c.id)
    with pytest.raises(Cancelled):c.save()
    assert c.store.count(c.id)==2
    assert len(c.store.frames(c.id,1,1))==1
    with c.store.db:c.store.db.execute("UPDATE jobs SET input='{}' WHERE id=?",(c.id,))
    with pytest.raises(ValueError,match='integrity'):c.store.job(c.id)


def test_frequencies_and_isotope(tmp_path):
    c=context(tmp_path,'freq',{'hessian':'finite_difference','nfree':4},r=1)
    f=frequencies(c);assert len(f['frequencies'])==1;assert f['frequencies'][0]>0
    c.atoms.set_masses([2.016,2.016]);d=frequencies(c)
    assert f['frequencies'][0]/d['frequencies'][0]==pytest.approx(np.sqrt(2),rel=1e-7)
    assert f['projected_dofs']==5;assert f['imaginary_modes']==[]


def test_constrained_and_scan(tmp_path):
    c=context(tmp_path,'constrained',constraints=[{'kind':'bond','atoms':[0,1],'value':1.2}])
    assert run(c)=='completed'
    assert coordinate(c.atoms.positions,[0,1])==pytest.approx(1.2,abs=1e-7)
    c.store.state(c.id,'completed')
    c=context(tmp_path,'scan',{'scans':[dict(kind='bond',atoms=[0,1],start=1,stop=1.3,points=4)]})
    assert run(c)=='completed'
    rows=c.store.artifact(c.id,'scan')['points'];assert len(rows)==4
    for row in rows:assert row['targets']==pytest.approx(row['achieved'],abs=1e-6)


def test_sella_ts_and_irc(tmp_path):
    pytest.importorskip('sella')
    c=context(tmp_path,'ts',{'sella_internal':False,'fmax':1e-5,'steps':200},r=1.48,double=True)
    assert run(c)=='completed';assert c.store.artifact(c.id,'saddle')['verified_first_order_saddle']
    c.store.state(c.id,'completed')
    c=context(tmp_path,'irc',{'fmax':.01,'steps':100,'endpoint_opt':True,'irc_dx':.05},r=1.5,double=True)
    assert run(c)=='completed'
    branches=c.store.artifact(c.id,'irc')['branches'];assert len(branches)==2
    assert branches[0]['points'][-1]['coordinate']>0;assert branches[1]['points'][-1]['coordinate']<0
    lengths=[coordinate(c.store.get_frame(c.id,b['points'][-1]['frame'])['positions'],[0,1]) for b in branches]
    assert min(lengths)<1.1 and max(lengths)>1.9
    assert all(b.get('endpoint_job') for b in branches)


@pytest.mark.parametrize('climb',[False,True])
@pytest.mark.parametrize('interpolation',['linear','idpp'])
def test_neb_mapping(tmp_path,climb,interpolation):
    product=dict(numbers=[1,1],positions=[[0,0,0],[2,0,0]],charge=0,multiplicity=1)
    c=context(tmp_path,'neb',dict(product=product,mapping=[0,1],images=5,interpolation=interpolation,climb=climb,steps=100,optimizer='FIRE',fmax=.02),r=1,double=True)
    assert run(c)=='completed'
    band=c.store.artifact(c.id,'neb')['history'][-1]['images'];assert [r['image'] for r in band]==list(range(5))
    for row in band:assert c.store.get_frame(c.id,row['frame'])['image']==row['image']
    assert not c.store.artifact(c.id,'neb')['verified_ts']

@pytest.mark.parametrize('ensemble',['nve','nvt'])
def test_md_and_exact_continuation(tmp_path,ensemble):
    c=context(tmp_path,'md',dict(ensemble=ensemble,steps=20,stride=5,timestep=.1,temperature=50),r=1)
    assert run(c)=='completed';cp=c.store.artifact(c.id,'checkpoint');assert cp['exact'] and cp['step']==20
    data=json.loads(json.dumps(c.data));data['continuation']={'job':c.id,'input_hash':c.store.job(c.id)['input_hash']}
    c.store.state(c.id,'completed');ident=c.store.submit(data);assert c.store.claim(ident)
    d=Context(c.store,ident,PairPotential(),tmp_path);assert run(d)=='completed'
    first=d.store.get_frame(d.id,0);last=c.store.get_frame(c.id,cp['frame'])
    np.testing.assert_allclose(first['positions'],last['positions'],atol=1e-14)
    np.testing.assert_allclose(first['velocities'],last['velocities'],atol=1e-14)
    assert d.store.artifact(d.id,'checkpoint')['step']==40
    if ensemble=='nve':assert c.store.artifact(c.id,'md')['max_energy_change_per_atom']<1e-5


def test_rmsd_does_not_reflect():
    p=np.array([[0,0,0],[1,0,0],[0,2,0],[0,0,3]])
    assert rmsd(p,p+5)<1e-12
    assert rmsd(p,p*np.array([-1,1,1]))>.1


def test_periodic_charge_identity_and_model_policies(tmp_path):
    from alder.mlip.registry import validate_model, model_path
    s=dict(numbers=[8,1,1],positions=[[0,0,0],[1,0,0],[0,1,0]],charge=0,multiplicity=1)
    c=dict(backend='mace',checkpoint='MACE-ANI-CC',device='cpu',precision='float64')
    assert validate_model(c,s,'sp')['name']=='MACE-ANI-CC'
    for change in [dict(pbc=[True,False,False]),dict(multiplicity=2),dict(ids=['x','x','y']),dict(masses=[1,-1,1])]:
        with pytest.raises(ValueError):snapshot(s|change,c,'sp')
    with pytest.raises(ValueError,match='charge'):validate_model(c,s|{'charge':1},'sp')
    with pytest.raises(ValueError,match='open-shell'):validate_model(c,s|{'multiplicity':3},'sp')
    with pytest.raises(ValueError,match='atomic numbers'):validate_model(c,s|{'numbers':[26,1,1]},'sp')
    with pytest.raises(ValueError,match='precision'):validate_model(c|{'device':'mps'},s,'sp')
    with pytest.raises(ValueError,match='double counting'):validate_model(c|{'corrections':'d3'},s,'sp')
    with pytest.raises(FileNotFoundError):model_path(c,tmp_path)


def test_optfreq_parent_only_completes_after_child(tmp_path):
    c=context(tmp_path,'optfreq',dict(fmax=1e-4),r=1.01);assert run(c)=='waiting';c.store.state(c.id,'waiting')
    child=c.store.artifact(c.id,'workflow')['child'];assert c.store.claim(child)
    ctx=Context(c.store,child,PairPotential(),tmp_path);assert run(ctx)=='completed';c.store.state(child,'completed')
    assert c.store.job(c.id)['status']=='completed'
    assert c.store.job(child)['input']['parent']['job']==c.id


def test_exact_md_matches_uninterrupted(tmp_path):
    first=context(tmp_path,'md',dict(steps=15,stride=5,ensemble='nvt',temperature=80,timestep=.15),r=1.05)
    assert run(first)=='completed';first.store.state(first.id,'completed')
    data=json.loads(json.dumps(first.data));data['continuation']={'job':first.id,'input_hash':first.store.job(first.id)['input_hash']}
    ident=first.store.submit(data);assert first.store.claim(ident);second=Context(first.store,ident,PairPotential(),tmp_path)
    assert run(second)=='completed';first.store.state(ident,'completed')
    full=context(tmp_path,'md',dict(steps=30,stride=5,ensemble='nvt',temperature=80,timestep=.15),r=1.05)
    assert run(full)=='completed'
    np.testing.assert_allclose(second.atoms.positions,full.atoms.positions,atol=1e-12)
    np.testing.assert_allclose(second.atoms.get_velocities(),full.atoms.get_velocities(),atol=1e-12)


def test_signed_torsion_constraint_crosses_wrap():
    from alder.mlip.engine import apply_constraints, residuals
    a=Atoms('CCCC',positions=[[-1,0,0],[0,0,0],[0,1,0],[1,1,.02]])
    original=a.positions.copy();d=[dict(kind='dihedral',atoms=[0,1,2,3],value=-179)]
    apply_constraints(a,d)
    assert coordinate(a.positions,[0,1,2,3])==pytest.approx(-179,abs=1e-5)
    assert residuals(a,d,original)[0]['residual']<1e-5


def test_nonfinite_and_memory_failure_keep_partial(tmp_path):
    c=context(tmp_path,'sp');c.save();assert c.store.count(c.id)==1
    class Broken(PairPotential):
        def calculate(self,*args,**kw):raise MemoryError('simulated allocation failure')
    from alder.mlip.engine import GuardedCalculator
    c.atoms.calc=GuardedCalculator(Broken(),c.check)
    with pytest.raises(MemoryError):c.save()
    assert c.store.count(c.id)==1


def test_constrained_frequencies_dofs(tmp_path):
    c=context(tmp_path,'freq',constraints=[dict(kind='freeze',atoms=[0])],r=1)
    f=frequencies(c)
    assert f['partial'];assert len(f['frequencies'])==1
    # One H is fixed: reduced mass doubles, stretching frequency drops by sqrt(2).
    c.data['constraints']=[];free=frequencies(c)
    assert free['frequencies'][0]/f['frequencies'][0]==pytest.approx(np.sqrt(2),rel=1e-6)

@pytest.mark.parametrize('failure,status',[(MemoryError('allocation failed'),'failed'),(InterruptedError('parent gone'),'interrupted')])
def test_worker_records_partial_failure(tmp_path,monkeypatch,failure,status):
    from alder.mlip import worker,adapters,engine
    store=Store(tmp_path/'worker.sqlite')
    data=snapshot(dict(numbers=[1,1],positions=[[0,0,0],[1.1,0,0]],charge=0,multiplicity=1),{},'sp')
    ident=store.submit(data)
    monkeypatch.setattr(adapters,'create',lambda *_:(PairPotential(),{'test':True}))
    def fail(ctx):ctx.save();raise failure
    monkeypatch.setattr(engine,'run',fail)
    import sys
    monkeypatch.setattr(sys,'argv',['worker','run','--db',str(store.path),'--job',ident,'--cache',str(tmp_path),'--workdir',str(tmp_path)])
    worker.main()
    assert store.job(ident)['status']==status;assert store.count(ident)==1
    assert status!='failed' or 'memory' in store.job(ident)['error'].lower()


def test_queue_claim_is_exclusive_and_redaction(tmp_path):
    from alder.mlip.environment import redact
    c=context(tmp_path,'sp');other=c.store.submit(c.data)
    second=Store(c.store.path);assert not second.claim(other)
    c.store.state(c.id,'completed');assert second.claim(other)
    assert 'secret' not in redact('token=secret hf_abcdef https://example.test/file?key=secret')
    assert redact('')==''


@pytest.mark.parametrize('smiles',['F[C@](Cl)(Br)I','F/C=C/F','F[C@]([2H])([H])Cl'])
def test_conformer_stereochemistry_mapping_and_dedup(tmp_path,smiles):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol=Chem.AddHs(Chem.MolFromSmiles(smiles));AllChem.EmbedMolecule(mol,randomSeed=42)
    structure=dict(numbers=[a.GetAtomicNum() for a in mol.GetAtoms()],masses=[a.GetMass() for a in mol.GetAtoms()],positions=mol.GetConformer().GetPositions().tolist(),charge=0,multiplicity=1,
        bonds=[dict(a=b.GetBeginAtomIdx(),b=b.GetEndAtomIdx(),order=b.GetBondTypeAsDouble()) for b in mol.GetBonds()])
    class Zero(Calculator):
        implemented_properties=['energy','forces']
        def calculate(self,atoms=None,properties=('energy','forces'),system_changes=all_changes):
            super().calculate(atoms,properties,system_changes);self.results=dict(energy=0.,forces=np.zeros_like(atoms.positions))
    data=snapshot(structure,{},'conformers',dict(candidates=4,rmsd=.5));store=Store(tmp_path/'conformers.sqlite');ident=store.submit(data);ctx=Context(store,ident,Zero(),tmp_path)
    assert run(ctx)=='completed';result=store.artifact(ident,'conformers')
    assert len(result['retained'])==1
    assert all(p['stereochemistry_preserved'] and not p['connectivity_changed'] for p in result['candidates'])
    assert store.job(ident)['input']['structure']['numbers']==structure['numbers']


def test_exact_restart_rejects_changed_environment(tmp_path):
    c=context(tmp_path,'md',dict(steps=2,stride=1),r=1)
    c.store.artifact(c.id,'provenance',{'software':{'ase':'original'}})
    assert run(c)=='completed';c.store.state(c.id,'completed')
    data=json.loads(json.dumps(c.data));data['continuation']={'job':c.id,'input_hash':c.store.job(c.id)['input_hash']}
    ident=c.store.submit(data);assert c.store.claim(ident)
    c.store.artifact(ident,'provenance',{'software':{'ase':'changed'}})
    with pytest.raises(ValueError,match='same recorded model'):
        run(Context(c.store,ident,PairPotential(),tmp_path))


def test_scan_preserves_failed_point_and_traversal(tmp_path,monkeypatch):
    from alder.mlip import engine
    c=context(tmp_path,'scan',{'scans':[dict(kind='bond',atoms=[0,1],start=1,stop=1.3,points=4)]})
    original=engine.optimize
    def fail_middle(ctx,**kwargs):
        if kwargs['point']==1:raise ValueError('test point failure')
        return original(ctx,**kwargs)
    monkeypatch.setattr(engine,'optimize',fail_middle)
    assert run(c)=='unconverged'
    rows=c.store.artifact(c.id,'scan')['points']
    assert [p['index'] for p in rows]==[[0],[1],[2],[3]]
    assert rows[1]['status']=='failed' and rows[1]['frame'] is None and rows[1]['energy'] is None
    assert rows[2]['status']=='converged'


def test_frozen_external_environment_isolated(monkeypatch,tmp_path):
    import os,sys
    from alder.mlip.environment import external_environment
    bundle=str(tmp_path/'bundle');original=str(tmp_path/'native')
    monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(sys,'_MEIPASS',bundle,raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH',bundle);monkeypatch.setenv('LD_LIBRARY_PATH_ORIG',original)
    monkeypatch.setenv('PYTHONPATH',bundle);monkeypatch.setenv('PATH',os.pathsep.join([bundle,bundle+os.sep+'Qt',original]))
    env=external_environment()
    assert env['LD_LIBRARY_PATH']==original and env['PATH']==original and 'PYTHONPATH' not in env
