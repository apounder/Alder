"""Read saved optimizer/MLIP trajectories without loading or running a calculator."""
import re

import numpy as np
from ase.io.extxyz import key_val_str_to_dict, read_extxyz
from ase.io.trajectory import Trajectory
from ase.units import Hartree, fs

from .data import Calculation, ELEMENTS, check_file

NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][-+]?\d+)?'
GEOMETRIC = re.compile(rf'^Iteration\s+\d+\s+Energy\s+({NUMBER})\s*$', re.I)


def _properties(comment, extended=False):
    match = GEOMETRIC.fullmatch(comment.strip())
    if match:
        return {'studio_energy_hartree': float(match[1].replace('D', 'E').replace('d', 'e')),
                'studio_source': 'geomeTRIC'}
    if extended or 'Properties=' in comment or 'Lattice=' in comment:
        return key_val_str_to_dict(comment)
    # Plain XYZ has no energy-unit convention. Only read an explicit unit.
    match = re.search(rf'\benergy\s*[:=]?\s*({NUMBER})\s*(Eh|Ha|Hartree|eV)\b', comment, re.I)
    if match:
        value = float(match[1].replace('D', 'E').replace('d', 'e'))
        return {'studio_energy_hartree': value / Hartree if match[2].lower() == 'ev' else value}
    return {}


def read_trajectory(path):
    path = check_file(path)
    frames, energies, forces, simulation_frames = [], [], [], []
    atomnos = None
    source = 'ASE / Sella trajectory' if path.suffix.lower() == '.traj' else 'XYZ trajectory'
    periodic = False
    def consume(images):
        nonlocal atomnos, source, periodic
        for atoms in images:
            numbers, points = atoms.numbers, atoms.positions
            if (not len(numbers) or points.shape != (len(numbers), 3) or not np.isfinite(points).all()
                    or np.any(numbers < 1) or np.any(numbers >= len(ELEMENTS))):
                raise ValueError('Trajectory contains unsupported atoms or invalid coordinates.')
            if atomnos is None:
                atomnos = numbers.copy()
            elif not np.array_equal(numbers, atomnos):
                raise ValueError('Every trajectory frame must contain the same elements in the same order. Open unrelated structures separately.')
            if len(frames) >= 100000 or (len(frames) + 1) * len(atomnos) > 5_000_000:
                raise ValueError('Trajectory exceeds 100,000 frames or 5 million atom positions. Export a shorter or sampled trajectory.')
            frame_input = dict(masses=atoms.get_masses().copy(), cell=atoms.cell.copy().array,
                               pbc=atoms.pbc.copy(), ase_constraints=[c.todict() for c in atoms.constraints])
            for key in ('charge', 'multiplicity', 'spin', 'mult'):
                if key in atoms.info: frame_input[key] = atoms.info[key]
            if atoms.has('momenta'):
                frame_input['velocities'] = atoms.get_velocities() * fs
            elif 'velocity' in atoms.arrays and atoms.info.get('velocity_unit') == 'angstrom/fs':
                frame_input['velocities'] = atoms.arrays['velocity'].copy()
            simulation_frames.append(frame_input)
            frames.append(points.copy())
            periodic |= bool(atoms.pbc.any())
            source = atoms.info.get('studio_source', source)
            # Read stored results directly: never call get_potential_energy().
            results = atoms.calc.results if atoms.calc else {}
            energy = atoms.info.get('studio_energy_hartree', np.nan)
            if 'energy' in results or 'energy' in atoms.info:
                value = results.get('energy', atoms.info.get('energy'))
                unit = str(atoms.info.get('energy_units', atoms.info.get('energy_unit', 'eV'))).lower()
                if unit not in {'ev', 'eh', 'ha', 'hartree'}:
                    raise ValueError(f'Unsupported trajectory energy unit: {unit}. Use eV or Hartree.')
                energy = float(value) / Hartree if unit == 'ev' else float(value)
            energies.append(float(energy))
            force = np.asarray(results.get('forces', atoms.arrays.get('forces', [])), dtype=float)
            forces.append(float(np.linalg.norm(force, axis=1).max())
                          if force.shape == points.shape and np.isfinite(force).all() else np.nan)
    try:
        if path.suffix.lower() == '.traj':
            # Modern ULM only; ASE's legacy pickle trajectory format is not used.
            with Trajectory(str(path), mode='r') as trajectory:
                consume(trajectory)
        else:
            with path.open(encoding='utf-8') as stream:
                consume(read_extxyz(stream, index=slice(None), properties_parser=lambda comment: _properties(comment, path.suffix.lower()=='.extxyz')))
    except (ValueError, OSError, IndexError, KeyError, TypeError) as error:
        raise ValueError(f'Could not read trajectory: {error}') from error
    if not frames:
        raise ValueError('No complete frames were found in this trajectory.')
    if source == 'XYZ trajectory' and np.isfinite(energies).any():
        source = 'Extended XYZ / saved energies'
    warnings = []
    if not np.isfinite(energies).all():
        warnings.append('Some frames have no saved energy with known units; those values remain blank.')
    if periodic:
        warnings.append('Periodic structure: displaying stored Cartesian positions only, without periodic images or cell wrapping.')
    summary = {'Program': source, 'Geometries': str(len(frames)), 'Energy': 'Saved potential energy (displayed in Hartree)',
               'Termination': 'Not determined from trajectory'}
    metadata = {'package': source, 'energy_label': 'Potential energy', 'max_forces': forces,
                'periodic': periodic, 'trajectory': True, 'simulation_frames': simulation_frames}
    return Calculation(path.name, atomnos, np.asarray(frames), np.asarray(energies), metadata, summary, warnings=warnings)
