"""Immutable molecular inputs; Angstrom, eV, fs, amu, and zero-based atom indices."""
from copy import deepcopy
import hashlib
import json
import numpy as np
from ase import Atoms
from ase.data import atomic_masses

UNITS = {'positions': 'angstrom', 'energy': 'eV', 'forces': 'eV/angstrom',
         'mass': 'amu', 'time': 'fs', 'velocities': 'angstrom/fs',
         'hessian': 'eV/angstrom^2', 'stress': 'eV/angstrom^3', 'frequency': 'cm^-1',
         'temperature': 'K', 'irc_coordinate': 'sqrt(amu)*angstrom'}
JOBS = {'sp', 'opt', 'constrained', 'freq', 'optfreq', 'scan', 'ts', 'irc', 'neb', 'md', 'conformers'}
DEFAULTS = dict(optimizer='BFGS', fmax=0.03, steps=300, maxstep=0.15, dt=0.1,
                hessian='auto', displacement=0.01, nfree=2, imaginary_threshold=20.,
                scans=[], images=7, interpolation='idpp', spring=0.1, climb=True,
                direction='both', irc_dx=0.1, irc_inner_fmax=0.01, irc_inner_steps=20,
                sella_eta=1e-4, sella_gamma=0.1, sella_delta=0.1, sella_internal=True,
                verify_ts=True, endpoint_opt=True, ensemble='nvt', timestep=0.5,
                temperature=300., friction=0.01, seed=61453, stride=10,
                md_max_temperature=10000., md_max_force=1000.,
                candidates=20, energy_window=0.5, rmsd=0.5, threads=2)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def wrap_angle(value):
    return (value + 180.) % 360. - 180.


def coordinate(positions, indices):
    p = np.asarray(positions, dtype=float)[indices]
    if len(p) == 2:
        result = np.linalg.norm(p[1]-p[0])
        if result < 1e-8:
            raise ValueError('Coincident atoms define a singular bond.')
        return float(result)
    a, b = p[0]-p[1], p[2]-p[1]
    if min(np.linalg.norm(a), np.linalg.norm(b)) < 1e-8:
        raise ValueError('Coincident atoms define a singular angle.')
    if len(p) == 3:
        return float(np.degrees(np.arccos(np.clip(a@b/np.linalg.norm(a)/np.linalg.norm(b), -1, 1))))
    if len(p) != 4:
        raise ValueError('A coordinate requires 2, 3, or 4 atom indices.')
    b1, b2, b3 = -a, b, p[3]-p[2]
    n1, n2 = np.cross(b1,b2), np.cross(b2,b3)
    if min(np.linalg.norm(n1), np.linalg.norm(n2)) < 1e-8:
        raise ValueError('Collinear atoms define a singular dihedral.')
    return float(wrap_angle(np.degrees(np.arctan2(np.cross(n1,n2)@(b2/np.linalg.norm(b2)), n1@n2))))


def jacobian(positions, constraints):
    p = np.asarray(positions, float)
    rows = []
    for constraint in constraints:
        ids = constraint['atoms']
        if constraint['kind'] == 'freeze':
            for atom in ids:
                for axis in range(3):
                    row = np.zeros(p.size); row[3*atom+axis] = 1; rows.append(row)
            continue
        row = np.zeros(p.size)
        for atom in ids:
            for axis in range(3):
                plus, minus = p.copy(), p.copy()
                plus[atom,axis] += 1e-5; minus[atom,axis] -= 1e-5
                delta = coordinate(plus, ids)-coordinate(minus, ids)
                row[3*atom+axis] = (wrap_angle(delta) if len(ids)==4 else delta)/2e-5
        rows.append(row)
    return np.asarray(rows).reshape((-1, p.size))


def validate_constraints(constraints, positions):
    n = len(positions); seen = set()
    for c in constraints:
        ids = c.get('atoms', [])
        kind = c.get('kind'); count = {'bond':2, 'angle':3, 'dihedral':4}.get(kind)
        if kind != 'freeze' and count is None:
            raise ValueError('Unknown constraint kind.')
        if not ids or any(type(i) is not int or not 0<=i<n for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('Constraint atom numbers must be unique and within the structure.')
        if kind == 'freeze':
            keys = [('freeze', i) for i in ids]
        else:
            if len(ids) != count:
                raise ValueError(f'{kind} needs {count} atoms.')
            keys = [(kind, min(tuple(ids), tuple(reversed(ids))))]
            actual = coordinate(positions, ids)
            target = c.get('value', actual)
            if not np.isfinite(target) or (count==2 and target<=0) or (count==3 and not 0.01<target<179.99):
                raise ValueError('Constraint target is nonfinite or singular.')
            if count==3 and not .01<actual<179.99:
                raise ValueError('Linear angle constraints are singular; select a different coordinate.')
            c['value'] = wrap_angle(target) if count==4 else float(target)
        if any(k in seen for k in keys):
            raise ValueError('Duplicate or conflicting constraints.')
        seen.update(keys)
    j = jacobian(positions, constraints)
    if len(j) and np.linalg.matrix_rank(j, tol=1e-6) != len(j):
        raise ValueError('Constraints are redundant or conflict with frozen atoms.')
    return constraints


def snapshot(structure, model, kind, settings=None, constraints=None, parent=None):
    s = deepcopy(structure)
    numbers = np.asarray(s.get('numbers', []))
    positions = np.asarray(s.get('positions', []), float)
    if not len(numbers) or numbers.ndim!=1 or not np.issubdtype(numbers.dtype,np.integer) or np.any((numbers<1)|(numbers>118)):
        raise ValueError('Choose a nonempty structure with valid atomic numbers.')
    if positions.shape != (len(numbers),3) or not np.isfinite(positions).all():
        raise ValueError('Coordinates must be finite, ordered Cartesian triples.')
    if np.any(s.get('pbc', False)):
        raise ValueError('These molecular workflows do not support periodic inputs. Cell/PBC data were retained; the job was rejected.')
    charge, mult = s.get('charge'), s.get('multiplicity')
    if type(charge) is not int or type(mult) is not int:
        raise ValueError('Explicit integer charge and spin multiplicity are required.')
    electrons = int(numbers.sum())-charge
    if electrons<1 or mult<1 or mult-1>electrons or (electrons-mult+1)%2:
        raise ValueError('Charge/multiplicity is inconsistent with the electron count.')
    masses = np.asarray(s.get('masses', atomic_masses[numbers]), float)
    if masses.shape!=(len(numbers),) or not np.isfinite(masses).all() or np.any(masses<=0):
        raise ValueError('Every atom must have a positive, finite mass.')
    s.update(numbers=numbers.tolist(), positions=positions.tolist(), masses=masses.tolist(),
             ids=s.get('ids', [f'a{i+1}' for i in range(len(numbers))]),
             cell=s.get('cell', np.zeros((3,3)).tolist()), pbc=[False]*3)
    if len(s['ids'])!=len(numbers) or len(set(s['ids']))!=len(numbers):
        raise ValueError('Atom identities must be unique and preserve atom order.')
    cell=np.asarray(s['cell'],float)
    if cell.shape!=(3,3) or not np.isfinite(cell).all():raise ValueError('Cell must be a finite 3×3 matrix, including for nonperiodic inputs.')
    if s.get('velocities') is not None:
        velocity=np.asarray(s['velocities'],float)
        if velocity.shape!=positions.shape or not np.isfinite(velocity).all():raise ValueError('Velocities must be finite ordered triples in Å/fs.')
    if kind not in JOBS:
        raise ValueError('Unknown calculation type.')
    opts = deepcopy(DEFAULTS); opts.update(deepcopy(settings or {}))
    for key in ('steps','stride','candidates','threads','irc_inner_steps','images'):
        if type(opts[key]) is not int or not 1<=opts[key]<=10000000:
            raise ValueError(f'{key} must be a positive integer.')
    if type(opts['seed']) is not int or not 0<=opts['seed']<2**31:
        raise ValueError('Seed must be between 0 and 2^31-1.')
    for key in ('fmax','maxstep','dt','displacement','irc_dx','irc_inner_fmax','sella_eta','sella_gamma','sella_delta','timestep','friction','rmsd','md_max_temperature','md_max_force'):
        if not np.isfinite(opts[key]) or opts[key]<=0:
            raise ValueError(f'{key} must be positive and finite.')
    if opts['optimizer'] not in ('BFGS','LBFGS','FIRE') or opts['nfree'] not in (2,4) or opts['hessian'] not in ('auto','analytical','finite_difference'):
        raise ValueError('Unsupported optimizer or Hessian setting.')
    if not np.isfinite(opts['temperature']) or opts['temperature']<0 or not np.isfinite(opts['energy_window']) or opts['energy_window']<0:
        raise ValueError('Temperature and energy window must be nonnegative.')
    if not np.isfinite(opts['imaginary_threshold']) or opts['imaginary_threshold']<0:
        raise ValueError('The significant-imaginary threshold must be finite and nonnegative.')
    for key in ('climb','verify_ts','endpoint_opt','sella_internal'):
        if type(opts[key]) is not bool:raise ValueError(f'{key} must be true or false.')
    if kind=='md' and opts['ensemble'] not in ('nve','nvt'):
        raise ValueError('Choose NVE or Langevin NVT.')
    if kind=='irc' and opts['direction'] not in ('forward','reverse','both'):
        raise ValueError('Choose forward, reverse, or both IRC directions.')
    constraints = validate_constraints(deepcopy(constraints or []), positions)
    if kind in ('irc','ts','neb','conformers') and constraints:
        raise ValueError('This workflow currently requires an unconstrained molecular input; use constrained optimization or scans for constraints.')
    if kind=='constrained' and not constraints:
        raise ValueError('Add at least one constraint for constrained optimization.')
    if kind=='scan':
        if not 1<=len(opts['scans'])<=2:
            raise ValueError('Select one or two scan coordinates.')
        if np.prod([scan.get('points',0) for scan in opts['scans']])>10000:raise ValueError('Limit a scan to 10,000 grid points per job.')
        for scan in opts['scans']:
            validate_constraints([deepcopy(scan)|{'value':scan['start']}], positions)
            validate_constraints([deepcopy(scan)|{'value':scan['stop']}], positions)
            if type(scan['points']) is not int or not 2<=scan['points']<=1000:
                raise ValueError('Scan point count must be 2–1000.')
        validate_constraints(constraints+[deepcopy(c)|{'value':coordinate(positions,c['atoms'])} for c in opts['scans']],positions)
    if kind=='neb':
        end=opts.get('product',{});mapping=opts.get('mapping',[])
        if sorted(mapping)!=list(range(len(numbers))) or len(end.get('numbers',[]))!=len(numbers):
            raise ValueError('NEB requires an explicit bijective atom mapping, one product index for each reactant atom.')
        if end.get('masses') is not None and not np.allclose(np.asarray(end['masses'])[mapping],masses,atol=1e-6):
            raise ValueError('Mapped NEB isotope masses must match.')
        if np.any(np.asarray(end['numbers'])[mapping]!=numbers) or np.any(end.get('pbc',False)):
            raise ValueError('NEB mapped elements must match and both endpoints must be molecular.')
        if end.get('charge')!=charge or end.get('multiplicity')!=mult:
            raise ValueError('NEB endpoints must have the same charge and multiplicity.')
        if np.asarray(end.get('positions',[])).shape!=positions.shape or not np.isfinite(end['positions']).all():
            raise ValueError('Invalid product coordinates.')
        if not 3<=opts['images']<=100 or opts['interpolation'] not in ('linear','idpp') or opts['spring']<=0:
            raise ValueError('NEB requires 3–100 total images, linear/IDPP interpolation, and positive spring.')
    result=dict(protocol=1, units=UNITS, structure=s, model=deepcopy(model), kind=kind,
                settings=opts, constraints=constraints, parent=deepcopy(parent))
    canonical(result)
    return result


def atoms_from_input(data):
    s=data['structure']
    a=Atoms(numbers=s['numbers'],positions=s['positions'],masses=s['masses'],cell=s['cell'],pbc=s['pbc'])
    a.info.update(charge=s['charge'], spin=s['multiplicity'], mult=s['multiplicity'])
    if s.get('velocities') is not None:
        from ase.units import fs
        v=np.asarray(s['velocities'],float)
        if v.shape!=a.positions.shape or not np.isfinite(v).all():
            raise ValueError('Invalid input velocities.')
        a.set_velocities(v/fs)
    return a
