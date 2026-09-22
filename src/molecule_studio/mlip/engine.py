"""Shared molecular workflows. No model-specific optimization or dynamics code."""
from copy import deepcopy
import itertools
import json
from pathlib import Path
import time
import numpy as np
from ase import units
from ase.calculators.calculator import Calculator, all_changes
from ase.constraints import FixAtoms, FixInternals, FixConstraint
from ase.optimize import BFGS, LBFGS, FIRE
from scipy.linalg import null_space
from .contract import atoms_from_input, coordinate, jacobian, snapshot, validate_constraints, wrap_angle


class Cancelled(Exception): pass


class GuardedCalculator(Calculator):
    """Check cancellation and numeric validity at every force evaluation, including line searches."""
    def __init__(self,base,check):
        super().__init__(); self.base=base; self.check=check
        self.implemented_properties=base.implemented_properties
    def calculate(self,atoms=None,properties=('energy','forces'),system_changes=all_changes):
        self.check();super().calculate(atoms,properties,system_changes)
        for prop in properties:
            self.base.get_property(prop,atoms)  # ASE owns cache invalidation (including atom-count/charge changes).
        self.results={k:np.array(v).copy() if isinstance(v,np.ndarray) else v for k,v in self.base.results.items()}
        for key in ('energy','forces'):
            if key in self.results and not np.isfinite(self.results[key]).all(): raise FloatingPointError(f'Nonfinite {key}; last valid frames are retained.')
    def get_hessian(self,atoms):
        self.check()
        if not hasattr(self.base,'get_hessian'): raise NotImplementedError('Calculator exposes no analytical Hessian.')
        h=np.asarray(self.base.get_hessian(atoms),dtype=float).reshape((3*len(atoms),3*len(atoms)))
        if not np.isfinite(h).all():raise FloatingPointError('Nonfinite analytical Hessian.')
        return (h+h.T)/2


class Context:
    def __init__(self,store,ident,calculator,workdir):
        self.store,self.id=store,ident
        self.data=store.job(ident)['input'];self.opts=self.data['settings']
        self.dir=Path(workdir)/ident; self.dir.mkdir(parents=True,exist_ok=True)
        self.calc=GuardedCalculator(calculator,self.check)
        self.atoms=atoms_from_input(self.data); self.atoms.calc=self.calc
        self.last_progress=0.
    def check(self):
        from .environment import process_alive
        if getattr(self,'parent_pid',None) and not process_alive(self.parent_pid):
            raise InterruptedError('Desktop process ended; last saved frames and checkpoint are retained.')
        if self.store.cancelled(self.id): raise Cancelled()
    def log(self,message): self.store.event(self.id,message)
    def progress(self,**data):
        self.check()
        if time.monotonic()-self.last_progress>.25:
            self.store.progress(self.id,**data);self.last_progress=time.monotonic()
    def save(self,atoms=None,checkpoint=None,**meta):
        self.check();a=self.atoms if atoms is None else atoms
        energy=float(a.get_potential_energy());forces=a.get_forces(apply_constraint=False)
        if forces.shape!=a.positions.shape or not np.isfinite(forces).all(): raise FloatingPointError('Invalid force array.')
        projected=a.get_forces()
        frame=dict(positions=a.positions.tolist(),energy=energy,forces=forces.tolist(),
            max_force=float(np.linalg.norm(forces,axis=1).max()),
            projected_max_force=float(np.linalg.norm(projected,axis=1).max()),
            masses=a.get_masses().tolist(),cell=a.cell.tolist(),pbc=a.pbc.tolist(),**meta)
        if a.has('momenta'):
            kinetic=float(a.get_kinetic_energy());frame.update(velocities=(a.get_velocities()*units.fs).tolist(),
                kinetic_energy=kinetic,total_energy=energy+kinetic,temperature=float(a.get_temperature()))
        for key in ('charges','spin_charges','dipole','stress'):
            if key in self.calc.results:frame[key]=np.asarray(self.calc.results[key]).tolist()
        return self.store.frame(self.id,frame,checkpoint)
    def child(self,kind,atoms=None,**settings):
        a=self.atoms if atoms is None else atoms
        structure=deepcopy(self.data['structure']);structure['positions']=a.positions.tolist()
        if a.has('momenta'):structure['velocities']=(a.get_velocities()*units.fs).tolist()
        opts=deepcopy(self.opts);opts.update(settings)
        data=snapshot(structure,self.data['model'],kind,opts,constraints=self.data['constraints'] if kind=='freq' else None,parent={'job':self.id,'frame':self.store.count(self.id)-1})
        ident=self.store.submit(data);self.log(f'Linked {kind} job queued: {ident}');return ident


class MolecularConstraints(FixConstraint):
    """ASE internal-coordinate SHAKE, with a rank-safe tangent projection.

    ASE 3.29 FixInternals.adjust_forces assumes six independent rigid modes,
    which fails on diatomics/linear molecules. Project only requested constraints.
    """
    def __init__(self, atoms, definitions):
        self.definitions=deepcopy(definitions);self.reference=atoms.positions.copy()
        self.frozen=[i for d in definitions if d['kind']=='freeze' for i in d['atoms']]
        internals={k:[] for k in ('bonds','angles_deg','dihedrals_deg')}
        for d in definitions:
            key={'bond':'bonds','angle':'angles_deg','dihedral':'dihedrals_deg'}.get(d['kind'])
            if key:internals[key].append([d['value'],d['atoms']])
        self.internal=FixInternals(**internals,epsilon=1e-10) if any(internals.values()) else None
    def get_removed_dof(self,atoms):return len(jacobian(atoms.positions,self.definitions))
    def adjust_positions(self,atoms,newpositions):
        for _ in range(100):
            if self.internal:self.internal.adjust_positions(atoms,newpositions)
            if self.frozen:newpositions[self.frozen]=self.reference[self.frozen]
            errors=[]
            for d in self.definitions:
                if d['kind']=='freeze':continue
                diff=coordinate(newpositions,d['atoms'])-d['value']
                errors.append(abs(wrap_angle(diff)) if d['kind']=='dihedral' else abs(diff))
            if max(errors,default=0)<1e-7:return
        raise ValueError('Constraint position projection did not converge; incompatible targets or geometry.')
    def adjust_forces(self,atoms,forces):
        j=jacobian(atoms.positions,self.definitions)
        forces[:]=(forces.ravel()-j.T@np.linalg.lstsq(j@j.T,j@forces.ravel(),rcond=1e-10)[0]).reshape((-1,3))
    def adjust_momenta(self,atoms,momenta):
        j=jacobian(atoms.positions,self.definitions);inv=1/np.repeat(atoms.get_masses(),3)
        momenta[:]=(momenta.ravel()-j.T@np.linalg.lstsq((j*inv)@j.T,j@(momenta.ravel()*inv),rcond=1e-10)[0]).reshape((-1,3))
    def todict(self):return dict(name='MoleculeStudioConstraints',kwargs=dict(definitions=self.definitions,reference=self.reference.tolist()))


def apply_constraints(atoms, definitions):
    if not definitions: atoms.set_constraint();return
    definitions=validate_constraints(deepcopy(definitions),atoms.positions)
    atoms.set_constraint(MolecularConstraints(atoms,definitions))
    atoms.set_positions(atoms.positions.copy())


def residuals(atoms,definitions,reference):
    rows=[]
    for d in definitions:
        if d['kind']=='freeze':
            value=float(np.linalg.norm(atoms.positions[d['atoms']]-np.asarray(reference)[d['atoms']],axis=1).max())
            rows.append(dict(kind='freeze',atoms=d['atoms'],residual=value,unit='angstrom'))
        else:
            actual=coordinate(atoms.positions,d['atoms']);delta=actual-d['value']
            rows.append(dict(kind=d['kind'],atoms=d['atoms'],target=d['value'],achieved=actual,
                             residual=abs(wrap_angle(delta)) if d['kind']=='dihedral' else abs(delta),unit='angstrom' if d['kind']=='bond' else 'degree'))
    return rows


def optimize(ctx,atoms=None,definitions=None,phase='optimization',**metadata):
    a=ctx.atoms if atoms is None else atoms; opts=ctx.opts
    definitions=ctx.data['constraints'] if definitions is None else definitions
    reference=a.positions.copy();apply_constraints(a,definitions)
    cls={'BFGS':BFGS,'LBFGS':LBFGS,'FIRE':FIRE}[opts['optimizer']]
    kwargs=dict(logfile=None,maxstep=opts['maxstep'])
    if cls is FIRE:kwargs['dt']=opts['dt']
    opt=cls(a,**kwargs)
    converged=False
    for converged in opt.irun(fmax=opts['fmax'],steps=opts['steps']):
        rows=residuals(a,definitions,reference)
        ctx.save(a,phase=phase,iteration=opt.nsteps,constraint_residuals=rows,**metadata)
        ctx.progress(phase=phase,iteration=opt.nsteps,maximum=opts['steps'],**metadata)
    rows=residuals(a,definitions,reference)
    feasible=all(r['residual']<(1e-5 if r['unit']=='angstrom' else 1e-3) for r in rows)
    return bool(converged and feasible), rows


def rigid_basis(atoms):
    p=atoms.positions-np.average(atoms.positions,axis=0,weights=atoms.get_masses())
    root=np.sqrt(atoms.get_masses())[:,None]
    translations=[(np.tile(v,(len(atoms),1))*root).ravel() for v in np.eye(3)]
    rotations=[(np.cross(v,p)*root).ravel() for v in np.eye(3)]
    return np.asarray(translations+rotations)


def frequencies(ctx,atoms=None,save=True):
    a=ctx.atoms if atoms is None else atoms;opts=ctx.opts;p=a.positions.copy();n=p.size
    constraints=ctx.data['constraints'];a.set_constraint()
    method=opts['hessian'];used='analytical'
    try:
        if method=='finite_difference':raise NotImplementedError()
        try:
            h=np.asarray(ctx.calc.get_hessian(a),float).reshape((n,n))
        except (NotImplementedError,AttributeError) as error:
            if method=='analytical':raise ValueError(f'Analytical Hessian unavailable: {error}') from error
            raise NotImplementedError() from error
    except NotImplementedError:
        used='finite_difference';h=np.zeros((n,n));delta=opts['displacement']
        ctx.log(f'Finite differences of full forces: {opts["nfree"]} points, displacement {delta} Å.')
        try:
            for col in range(n):
                samples={}
                for factor in ((-1,1) if opts['nfree']==2 else (-2,-1,1,2)):
                    ctx.check();q=p.copy().ravel();q[col]+=factor*delta;a.set_positions(q.reshape((-1,3)))
                    samples[factor]=a.get_forces(apply_constraint=False).ravel()
                h[:,col]=((samples[-1]-samples[1])/(2*delta) if opts['nfree']==2 else
                          (samples[2]-8*samples[1]+8*samples[-1]-samples[-2])/(12*delta))
                ctx.progress(phase='Hessian',iteration=col+1,maximum=n)
        finally:a.set_positions(p)
    if not np.isfinite(h).all():raise FloatingPointError('Nonfinite Hessian.')
    antisymmetric=float(np.max(np.abs(h-h.T)));h=(h+h.T)/2
    mass=np.repeat(a.get_masses(),3);root=np.sqrt(mass)
    rows=rigid_basis(a)
    if constraints:
        # The Hessian of the Lagrangian supplies the curvature of nonlinear constraints.
        jcart=jacobian(p,constraints);j=jcart/root
        multipliers=np.linalg.lstsq(jcart@jcart.T,jcart@a.get_forces(apply_constraint=False).ravel(),rcond=1e-10)[0]
        for col in range(n):
            plus=p.copy().ravel();minus=p.copy().ravel();plus[col]+=1e-4;minus[col]-=1e-4
            dg=(jacobian(plus.reshape((-1,3)),constraints)-jacobian(minus.reshape((-1,3)),constraints))/2e-4
            h[:,col]+=multipliers@dg
        h=(h+h.T)/2
        rigid=null_space(null_space(rows).T)
        allowed_rigid=rigid@null_space(j@rigid,rcond=1e-8)
        rows=np.vstack([allowed_rigid.T,j])
    basis=null_space(rows,rcond=1e-8)
    eig,v=np.linalg.eigh(basis.T@(h/root[:,None]/root[None,:])@basis)
    conversion=units._hbar*1e10/np.sqrt(units._e*units._amu)/units.invcm
    freq=np.sign(eig)*np.sqrt(np.abs(eig))*conversion
    modes=((basis@v)/root[:,None]).T.reshape((-1,len(a),3))
    result=dict(frequencies=freq.tolist(),modes=modes.tolist(),hessian=h.tolist(),positions=p.tolist(),
        masses=a.get_masses().tolist(),method=used,displacement=opts['displacement'] if used=='finite_difference' else None,
        nfree=opts['nfree'] if used=='finite_difference' else None,projected_dofs=int(n-basis.shape[1]),
        partial=bool(constraints),constraints=constraints,antisymmetry=antisymmetric,
        imaginary_modes=[int(i) for i in np.flatnonzero(freq < -opts['imaginary_threshold'])],
        imaginary_threshold=opts['imaginary_threshold'],max_force=float(np.linalg.norm(a.get_forces(),axis=1).max()))
    if save:
        ctx.store.artifact(ctx.id,'frequencies',result)
        ctx.save(a,phase='frequencies')
    return result


def scans(ctx):
    axes=ctx.opts['scans'];values=[np.linspace(d['start'],d['stop'],d['points']) for d in axes]
    points=[];last=ctx.atoms.positions.copy();all_ok=True
    ctx.log('Scan traversal: row-major (last coordinate fastest); each point starts from last converged geometry, otherwise last successful geometry; no interpolation.')
    for point,index in enumerate(itertools.product(*[range(len(v)) for v in values])):
        targets=[float(values[k][i]) for k,i in enumerate(index)]
        defs=deepcopy(ctx.data['constraints'])+[dict(kind=d['kind'],atoms=d['atoms'],value=v) for d,v in zip(axes,targets)]
        ctx.atoms.set_constraint();ctx.atoms.set_positions(last)
        row=dict(index=list(index),targets=targets,status='failed',frame=None,energy=None,achieved=None)
        before=ctx.store.count(ctx.id)
        try:
            ok,res=optimize(ctx,definitions=defs,phase='scan',point=point,grid=list(index),targets=targets)
            row.update(status='converged' if ok else 'unconverged',frame=ctx.store.count(ctx.id)-1,
                achieved=[coordinate(ctx.atoms.positions,d['atoms']) for d in axes],
                energy=float(ctx.atoms.get_potential_energy()),residuals=res)
            if ok:last=ctx.atoms.positions.copy()
            all_ok &= ok
        except (Cancelled,MemoryError,InterruptedError):raise
        except Exception as error:
            row['error']=str(error) or type(error).__name__ or type(error).__name__;ctx.log(f'Scan point {index} failed: {row["error"]}');all_ok=False
            if ctx.store.count(ctx.id)>before:
                frame=ctx.store.get_frame(ctx.id,ctx.store.count(ctx.id)-1)
                row.update(frame=ctx.store.count(ctx.id)-1,energy=frame['energy'],achieved=[coordinate(frame['positions'],d['atoms']) for d in axes])
        points.append(row);ctx.store.artifact(ctx.id,'scan',dict(axes=axes,points=points,traversal='row-major; last converged geometry'))
    return 'completed' if all_ok else 'unconverged'


def transition_state(ctx):
    from sella import Sella
    o=ctx.opts
    opt=Sella(ctx.atoms,logfile=None,internal=o['sella_internal'],order=1,eta=o['sella_eta'],
              gamma=o['sella_gamma'],delta0=o['sella_delta'],
              hessian_function=ctx.calc.get_hessian if hasattr(ctx.calc.base,'get_hessian') and o['hessian']!='finite_difference' else None)
    converged=False
    for converged in opt.irun(fmax=o['fmax'],steps=o['steps']):
        ctx.save(phase='TS refinement',iteration=opt.nsteps)
        ctx.progress(phase='TS refinement',iteration=opt.nsteps,maximum=o['steps'])
    result=dict(search_converged=bool(converged),verified_first_order_saddle=False)
    if o['verify_ts']:
        vib=frequencies(ctx)
        result.update(imaginary_modes=vib['imaginary_modes'],verified_first_order_saddle=bool(converged and not vib['partial'] and len(vib['imaginary_modes'])==1))
    ctx.store.artifact(ctx.id,'saddle',result)
    ctx.log('Verified first-order saddle.' if result['verified_first_order_saddle'] else 'Not a verified first-order saddle; inspect frequency results and convergence.')
    return 'completed' if converged else 'unconverged'


def irc(ctx):
    from sella import IRC
    o=ctx.opts
    vib=frequencies(ctx)
    if len(vib['imaginary_modes'])!=1 or vib['max_force']>o['fmax']:
        raise ValueError('IRC requires a stationary input with one significant imaginary frequency; refine/verify the TS first.')
    ts=ctx.atoms.positions.copy();branches=[];all_ok=True
    solver=IRC(ctx.atoms,logfile=None,dx=o['irc_dx'],eta=o['sella_eta'],gamma=o['sella_gamma'],ninner_iter=o['irc_inner_steps'],
               hessian_function=ctx.calc.get_hessian if hasattr(ctx.calc.base,'get_hessian') and o['hessian']!='finite_difference' else None)
    for direction in (('forward','reverse') if o['direction']=='both' else (o['direction'],)):
        ctx.atoms.set_positions(ts);last=ts.copy();distance=0.;points=[];ok=False
        try:
            for ok in solver.irun(fmax=o['fmax'],fmax_inner=o['irc_inner_fmax'],steps=o['steps'],direction=direction):
                p=ctx.atoms.positions.copy();distance+=float(np.sqrt(np.sum(ctx.atoms.get_masses()[:,None]*(p-last)**2)));last=p
                signed=distance if direction=='forward' else -distance
                frame=ctx.save(phase='IRC',direction=direction,coordinate=signed,iteration=solver.nsteps)
                points.append(dict(frame=frame,coordinate=signed,energy=float(ctx.atoms.get_potential_energy())))
                ctx.store.artifact(ctx.id,'irc',dict(branches=branches+[dict(direction=direction,points=points,termination='running')]))
                ctx.progress(phase='IRC '+direction,iteration=solver.nsteps,maximum=o['steps'])
                # Sella's unprojected IRC Hessian may retain tiny negative rigid-body
                # eigenvalues at a molecular minimum, especially with float32 forces.
                # Verify stationarity and internal curvature before ending that branch.
                if len(points)>1 and np.linalg.norm(ctx.atoms.get_forces(),axis=1).max()<o['fmax']:
                    endpoint=frequencies(ctx,save=False)
                    if not endpoint['imaginary_modes']:
                        ctx.store.artifact(ctx.id,'endpoint_frequencies_'+direction,endpoint)
                        ok=True;break
            branch=dict(direction=direction,points=points,termination='stationary_molecular_minimum' if ok else 'step_limit')
        except (Cancelled,MemoryError,InterruptedError):raise
        except Exception as error:
            branch=dict(direction=direction,points=points,termination='failed',error=str(error) or type(error).__name__);ctx.log(f'IRC {direction}: {str(error) or type(error).__name__}')
        if o['endpoint_opt'] and points:branch['endpoint_job']=ctx.child('opt',direction=direction)
        branches.append(branch);all_ok &= bool(ok)
        ctx.store.artifact(ctx.id,'irc',dict(branches=branches))
    return 'completed' if all_ok else 'unconverged'


def neb(ctx):
    from ase.mep import NEB
    o=ctx.opts;a=ctx.atoms
    product=np.asarray(o['product']['positions'])[o['mapping']]
    images=[a.copy() for _ in range(o['images'])];images[-1].positions[:]=product
    for img in images:img.calc=ctx.calc
    band=NEB(images,k=o['spring'],climb=o['climb'],allow_shared_calculator=True,method='aseneb')
    band.interpolate(method=o['interpolation'],apply_constraint=False)
    cls={'BFGS':BFGS,'LBFGS':LBFGS,'FIRE':FIRE}[o['optimizer']]
    opt=cls(band,logfile=None,maxstep=o['maxstep'],**({'dt':o['dt']} if cls is FIRE else {}))
    history=[];ok=False
    for ok in opt.irun(fmax=o['fmax'],steps=o['steps']):
        rows=[];distance=0.;previous=images[0].positions
        for index,img in enumerate(images):
            distance+=float(np.linalg.norm(img.positions-previous));previous=img.positions
            frame=ctx.save(img,phase='NEB',band_iteration=opt.nsteps,image=index,coordinate=distance)
            rows.append(dict(image=index,frame=frame,coordinate=distance,energy=float(img.get_potential_energy())))
        history=[dict(iteration=opt.nsteps,images=rows)]
        ctx.store.artifact(ctx.id,'neb',dict(history=history,history_in_frames=True,climbing=o['climb'],mapping=o['mapping'],verified_ts=False))
        ctx.progress(phase='NEB',iteration=opt.nsteps,maximum=o['steps'])
    return 'completed' if ok else 'unconverged'


def dynamics(ctx):
    from ase.md.verlet import VelocityVerlet
    from ase.md.langevin import Langevin
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary, ZeroRotation
    a=ctx.atoms;o=ctx.opts;rng=np.random.default_rng(o['seed']);apply_constraints(a,ctx.data['constraints'])
    continuation=ctx.data.get('continuation');offset=0
    if continuation:
        cp=ctx.store.artifact(continuation['job'],'checkpoint')
        if cp is None or cp['kind']!='md' or cp['input_hash']!=continuation['input_hash']:
            raise ValueError('No compatible exact MD checkpoint exists.')
        source=ctx.store.job(continuation['job'])['input']
        previous=ctx.store.artifact(continuation['job'],'provenance');current=ctx.store.artifact(ctx.id,'provenance')
        if previous!=current:raise ValueError('Exact continuation requires the same recorded model, software, device, precision and corrections. Use geometry restart if they changed.')
        for key in ('model','constraints','structure'):
            if source[key]!=ctx.data[key]:raise ValueError('Exact continuation requires identical model, atom identities, masses, charge/spin and constraints.')
        if source['settings']!=o:raise ValueError('Exact continuation requires identical integrator, thermostat, and numerical settings.')
        frame=ctx.store.get_frame(continuation['job'],cp['frame'])
        a.set_positions(frame['positions'],apply_constraint=False);a.set_velocities(np.asarray(frame['velocities'])/units.fs)
        rng.bit_generator.state=cp['rng'];offset=cp['step']
    elif not a.has('momenta'):
        if o['temperature']==0:a.set_velocities(np.zeros_like(a.positions))
        else:
            MaxwellBoltzmannDistribution(a,temperature_K=o['temperature'],rng=rng)
            if len(a)>1 and not ctx.data['constraints']:
                Stationary(a,preserve_temperature=False)
                # Pseudoinverse is well-defined for linear molecules and single-axis inertia.
                p=a.positions-a.get_center_of_mass();m=a.get_masses()
                inertia=sum(mass*((v@v)*np.eye(3)-np.outer(v,v)) for mass,v in zip(m,p))
                omega=np.linalg.pinv(inertia)@np.sum(np.cross(p,a.get_momenta()),axis=0)
                a.set_velocities(a.get_velocities()-np.cross(omega,p))
    kwargs=dict(timestep=o['timestep']*units.fs,logfile=None)
    md=(VelocityVerlet(a,**kwargs) if o['ensemble']=='nve' else
        Langevin(a,temperature_K=o['temperature'],friction=o['friction']/units.fs,rng=rng,fixcm=False,**kwargs))
    initial=float(a.get_total_energy());maxdrift=0.;last_saved=-1
    for _ in md.irun(steps=o['steps']):
        step=offset+md.nsteps;ctx.check()
        energy=float(a.get_total_energy());temp=float(a.get_temperature());force=float(np.linalg.norm(a.get_forces(),axis=1).max())
        maxdrift=max(maxdrift,abs(energy-initial)/len(a))
        if not np.isfinite([energy,temp,force]).all() or temp>o['md_max_temperature'] or force>o['md_max_force']:
            raise FloatingPointError('MD numerical safety threshold exceeded; partial trajectory and last exact checkpoint retained.')
        if md.nsteps%o['stride']==0 or md.nsteps==o['steps']:
            cp=dict(kind='md',step=step,rng=rng.bit_generator.state,input_hash=ctx.store.job(ctx.id)['input_hash'],
                    integrator='VelocityVerlet' if o['ensemble']=='nve' else 'Langevin',exact=True)
            ctx.save(checkpoint=cp,phase='MD',iteration=step,time=step*o['timestep'],energy_drift_per_atom=(energy-initial)/len(a))
            last_saved=step
        ctx.progress(phase='MD',iteration=md.nsteps,maximum=o['steps'],temperature=temp,total_energy=energy,potential_energy=float(a.get_potential_energy()),kinetic_energy=float(a.get_kinetic_energy()))
    ctx.store.artifact(ctx.id,'md',dict(ensemble=o['ensemble'],max_energy_change_per_atom=maxdrift,steps=o['steps'],
        final_step=last_saved,thermostat='none' if o['ensemble']=='nve' else 'Langevin',friction_fs_inverse=o['friction']))
    return 'completed'


def rmsd(p,q):
    p=np.asarray(p)-np.mean(p,axis=0);q=np.asarray(q)-np.mean(q,axis=0)
    u,_,vt=np.linalg.svd(p.T@q);rot=u@np.diag([1,1,np.linalg.det(u@vt)])@vt
    return float(np.sqrt(np.mean(np.sum((p@rot-q)**2,axis=1))))


def conformers(ctx):
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdDetermineBonds
    from ase.data import atomic_masses
    s=ctx.data['structure'];o=ctx.opts
    # The supplied graph and explicit atom mapping, not a re-parsed SMILES order, define candidates.
    graph=s.get('bonds')
    if graph is None:raise ValueError('Conformer search requires a molecular graph; use Build or supply explicit bonds. XYZ alone has no bond orders.')
    rw=Chem.RWMol()
    for i,z in enumerate(s['numbers']):
        atom=Chem.Atom(int(z));atom.SetAtomMapNum(i+1)
        # Isotope masses must distinguish isotope-dependent stereocenters in RDKit.
        if min(abs(s['masses'][i]-atomic_masses[z]),abs(s['masses'][i]-Chem.GetPeriodicTable().GetAtomicWeight(int(z))))>1e-3:
            isotope=int(round(s['masses'][i]));mass=Chem.GetPeriodicTable().GetMassForIsotope(int(z),isotope)
            if mass<=0 or abs(mass-s['masses'][i])>.01:
                raise ValueError('Conformer sampling requires standard atomic or recognized isotope masses; arbitrary effective masses cannot define isotope stereochemistry.')
            atom.SetIsotope(isotope)
        atom.SetFormalCharge(int(s.get('formal_charges',[0]*len(s['numbers']))[i]));rw.AddAtom(atom)
    for b in graph:
        if b.get('kind') in ('ts','dative'):raise ValueError('RDKit conformer sampling currently requires ordinary molecular bond orders.')
        rw.AddBond(b['a'],b['b'],{1:Chem.BondType.SINGLE,2:Chem.BondType.DOUBLE,3:Chem.BondType.TRIPLE,1.5:Chem.BondType.AROMATIC}[b['order']])
    mol=rw.GetMol();Chem.SanitizeMol(mol)
    if sum(a.GetNumImplicitHs() for a in mol.GetAtoms()):raise ValueError('Conformer sampling needs explicit hydrogens; add them in Build before submitting.')
    conf=Chem.Conformer(len(s['numbers']))
    for i,p in enumerate(s['positions']):conf.SetAtomPosition(i,p)
    mol.AddConformer(conf);Chem.AssignStereochemistryFrom3D(mol,confId=0,replaceExistingTags=True)
    original=Chem.MolToSmiles(mol,isomericSmiles=True)
    params=AllChem.ETKDGv3();params.randomSeed=o['seed'];params.numThreads=1;params.enforceChirality=True;params.pruneRmsThresh=-1;params.timeout=30
    ids=list(AllChem.EmbedMultipleConfs(mol,numConfs=o['candidates'],params=params))
    ctx.check();rows=[];retained=[]
    original_edges={tuple(sorted((b['a'],b['b']))) for b in graph}
    for index,cid in enumerate(ids):
        ctx.check();a=ctx.atoms.copy();a.calc=ctx.calc;a.positions[:]=mol.GetConformer(cid).GetPositions()
        row=dict(candidate=index,status='failed',frame=None,energy=None)
        try:
            ok,_=optimize(ctx,a,definitions=[],phase='conformer',candidate=index)
            frame=ctx.store.count(ctx.id)-1;energy=float(a.get_potential_energy())
            final=Chem.Mol(mol);final.RemoveAllConformers();c=Chem.Conformer(len(a))
            for i,p in enumerate(a.positions):c.SetAtomPosition(i,p)
            final.AddConformer(c);Chem.AssignStereochemistryFrom3D(final,replaceExistingTags=True)
            same_stereo=Chem.MolToSmiles(final,isomericSmiles=True)==original
            connect=Chem.Mol(final);rdDetermineBonds.DetermineConnectivity(connect)
            edges={tuple(sorted((b.GetBeginAtomIdx(),b.GetEndAtomIdx()))) for b in connect.GetBonds()}
            changed=edges!=original_edges
            row.update(status='optimized' if ok else 'unconverged',frame=frame,energy=energy,connectivity_changed=changed,stereochemistry_preserved=same_stereo)
            if ok and not changed and same_stereo:retained.append((energy,a.positions.copy(),index,frame))
        except (Cancelled,MemoryError,InterruptedError):raise
        except Exception as error:row['error']=str(error) or type(error).__name__
        rows.append(row);ctx.store.artifact(ctx.id,'conformers',dict(candidates=rows,retained=[],requested=o['candidates'],embedded=len(ids)))
    selected=[];heavy=np.flatnonzero(np.asarray(s['numbers'])!=1)
    if len(heavy)==0:heavy=np.arange(len(s['numbers']))
    for energy,p,index,frame in sorted(retained,key=lambda x:x[0]):
        if energy>min(x[0] for x in retained)+o['energy_window']:continue
        if any(rmsd(p[heavy],x[1][heavy])<o['rmsd'] for x in selected):continue
        selected.append((energy,p,index,frame))
    ctx.store.artifact(ctx.id,'conformers',dict(candidates=rows,retained=[dict(rank=i+1,energy=e,candidate=c,frame=f) for i,(e,_,c,f) in enumerate(selected)],
        requested=o['candidates'],embedded=len(ids),criterion='Heavy-atom mapped proper-rotation RMSD; no symmetry permutations; sampled search, not a guaranteed global minimum.'))
    return 'completed' if selected else 'unconverged'


def run(ctx):
    kind=ctx.data['kind']
    if kind=='sp':ctx.save(phase='Single point');return 'completed'
    if kind in ('opt','constrained','optfreq'):
        ok,rows=optimize(ctx)
        ctx.store.artifact(ctx.id,'optimization',dict(converged=ok,residuals=rows,termination='force_converged' if ok else 'step_limit_or_constraint_residual'))
        if kind=='optfreq' and ok:
            child=ctx.child('freq')
            ctx.store.artifact(ctx.id,'workflow',dict(child=child,stage='frequencies'))
            return 'waiting'
        elif kind=='optfreq':ctx.log('Frequency child not started because optimization did not converge.')
        return 'completed' if ok else 'unconverged'
    if kind=='freq':frequencies(ctx);return 'completed'
    return {'scan':scans,'ts':transition_state,'irc':irc,'neb':neb,'md':dynamics,'conformers':conformers}[kind](ctx)
