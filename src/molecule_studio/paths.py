"""Reported scan and IRC points with explicit trajectory associations."""
from dataclasses import dataclass, replace
from pathlib import Path
import re

import numpy as np
from cclib.parser.utils import PeriodicTable, convertor


@dataclass
class ReactionPath:
    kind: str
    labels: list
    parameters: np.ndarray  # [point, coordinate]
    energies: np.ndarray  # Hartree
    steps: np.ndarray  # indices into Calculation.coords; -1 = unavailable
    relative: bool = False  # old ORCA summaries may only print E - E(TS)


class PathTracker:
    def __init__(self):
        self.irc = []
        self.direction = 1
        self.completed = []

    def observe(self, line, step):
        if 'Optimization completed.' in line or 'THE OPTIMIZATION HAS CONVERGED' in line:
            self.completed.append(step)
        if 'path direction' in line:
            self.direction = -1 if 'REVERSE' in line or 'BACKWARD' in line else 1
        if re.search(r'Point Number:\s+0\s+Path Number:', line) and not self.irc:
            self.irc.append((0., step))
        if 'NET REACTION COORDINATE UP TO THIS POINT' in line:
            self.irc.append((self.direction * abs(float(line.split('=')[-1])), step))


def coordinate(name, coords, program):
    """Evaluate an explicitly identified bond/angle/dihedral for scan matching."""
    match = re.fullmatch(r'\s*(R|B|A|D|Bond|Angle|Dihedral)\s*\(([^)]+)\)\s*', name)
    if not match:
        return None, name
    indices = [int(v) - (1 if program == 'Gaussian' else 0) for v in re.findall(r'\d+', match[2])]
    if not indices or min(indices) < 0 or max(indices) >= coords.shape[1]:
        return None, name
    p = coords[:, indices, :]
    if len(indices) == 2:
        return np.linalg.norm(p[:, 0]-p[:, 1], axis=1), name + ' / Å'
    if len(indices) == 3:
        a, b = p[:, 0]-p[:, 1], p[:, 2]-p[:, 1]
        denominator = np.linalg.norm(a, axis=1)*np.linalg.norm(b, axis=1)
        return np.degrees(np.arccos(np.clip(np.sum(a*b, axis=1)/np.maximum(denominator, 1e-15), -1, 1))), name + ' / °'
    if len(indices) == 4:
        b0, b1, b2 = p[:, 0]-p[:, 1], p[:, 2]-p[:, 1], p[:, 3]-p[:, 2]
        b1 = b1/np.maximum(np.linalg.norm(b1, axis=1)[:, None], 1e-15)
        v = b0 - np.sum(b0*b1, axis=1)[:, None]*b1
        w = b2 - np.sum(b2*b1, axis=1)[:, None]*b1
        return np.degrees(np.arctan2(np.sum(np.cross(b1, v)*w, axis=1), np.sum(v*w, axis=1))), name + ' / °'
    return None, name


def read_reaction_path(data, coords, energies, tracker, path, warnings):
    if tracker.irc:
        rows = sorted((x, step) for x, step in tracker.irc if 0 <= step < len(coords))
        steps = np.array([step for _, step in rows], dtype=int)
        return ReactionPath('IRC', ['Reaction coordinate / √amu bohr'],
                            np.array([[x] for x, _ in rows]), energies[steps].copy(), steps), None
    if hasattr(data, 'scanparm') and hasattr(data, 'scannames'):
        parameters = np.asarray(data.scanparm, dtype=float).T
        names = list(data.scannames)
        if parameters.ndim != 2 or parameters.shape[1] != len(names) or not len(parameters):
            warnings.append('Incomplete scan coordinate table; the full geometry trajectory is still available.')
            return None, None
        n = len(parameters)
        values = np.asarray(getattr(data, 'scanenergies', []), dtype=float)
        values = convertor(values, 'eV', 'hartree') if values.shape == (n,) else np.full(n, np.nan)
        steps = np.full(n, -1, dtype=int)
        status = np.asarray(getattr(data, 'optstatus', []), dtype=int)
        candidates = (np.asarray(tracker.completed, dtype=int) if tracker.completed else
                      np.flatnonzero(status & 4) if len(status) else np.arange(len(coords)))
        candidates = candidates[candidates < len(coords)]
        labels, evaluated = [], []
        for name in names:
            measured, label = coordinate(name, coords, data.metadata.get('package'))
            labels.append(label)
            evaluated.append(measured)
        if all(v is not None for v in evaluated):
            actual = np.array(evaluated).T
            used = set()
            for i, parameter in enumerate(parameters):
                delta = np.abs(actual[candidates] - parameter)
                for dim, name in enumerate(names):
                    if name.strip().startswith(('D', 'Dihedral')):
                        delta[:, dim] = np.abs((delta[:, dim]+180) % 360-180)
                    delta[:, dim] /= .002 if labels[dim].endswith('Å') else .05
                matches = [int(candidates[j]) for j in np.flatnonzero(np.all(delta <= 1, axis=1)) if int(candidates[j]) not in used]
                if matches:
                    steps[i] = matches[0]
                    used.add(matches[0])
        elif len(candidates) == n:
            # No atom definition (e.g. Gaussian Z-matrix variable D7).
            # Positional mapping is safe only when the complete counts agree.
            steps[:] = candidates
        for i, step in enumerate(steps):
            if step >= 0 and np.isfinite(energies[step]):
                # Gaussian may print all asterisks in a large-energy summary.
                # A matched converged geometry supplies the full SCF precision.
                if not np.isfinite(values[i]) or abs(values[i]-energies[step]) < 5e-5:
                    values[i] = energies[step]
        if np.any(steps < 0):
            warnings.append('Some scan points have no confirmed converged geometry; they remain unlinked.')
        return ReactionPath('Scan', labels, parameters, values, steps), None
    if data.metadata.get('package') == 'ORCA':
        return read_orca_irc(path, energies)
    return None, None


def read_orca_irc(path, energies):
    rows, ts, active, relative, companion = [], None, False, False, None
    with Path(path).open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            if 'Storing full IRC trajectory in' in line:
                filename = line.split()[-1].replace('\\', '/').split('/')[-1]
                companion = Path(path).with_name(filename)
            if 'IRC PATH SUMMARY' in line:
                rows, ts, active = [], None, True
            elif active:
                fields = line.split()
                if fields and fields[0] == 'Step':
                    relative = 'E(Eh)' not in line
                elif fields and fields[0].isdigit() and len(fields) >= 2:
                    try:
                        value = float(fields[1])
                    except ValueError:
                        continue
                    rows.append((int(fields[0]), value / 627.509474 if relative else value))
                    if 'TS' in line:
                        ts = int(fields[0])
                elif rows:
                    active = False
    if not rows:
        return None, None
    points = np.array([[number-(ts or 0)] for number, _ in rows], dtype=float)
    values = np.array([energy for _, energy in rows])
    steps = np.full(len(rows), -1, dtype=int)
    if not relative:
        for i, energy in enumerate(values):
            matches = np.flatnonzero(np.isfinite(energies) & (np.abs(energies-energy) < 5e-7))
            if len(matches) == 1:
                steps[i] = matches[0]
    if companion is None:
        companion = Path(path).with_name(Path(path).stem + '_IRC_Full_trj.xyz')
    return ReactionPath('IRC', ['IRC step (TS = 0)' if ts is not None else 'IRC step'], points, values, steps, relative), companion


def attach_irc_trajectory(calculation, path):
    """Attach ORCA's full, path-ordered XYZ; never treat a frame as a new atom."""
    reaction = calculation.reaction_path
    if reaction is None or reaction.kind != 'IRC':
        raise ValueError('Load an IRC calculation before attaching its full XYZ trajectory.')
    symbols = PeriodicTable().element
    expected = [symbols[int(z)] for z in calculation.atomnos]
    frames = []
    with Path(path).open(encoding='utf-8', errors='replace') as stream:
        while True:
            line = stream.readline()
            if not line:
                break
            if not line.strip():
                continue
            try:
                count = int(line)
                if count != len(expected):
                    raise ValueError('IRC trajectory atom count differs from the output.')
                comment = stream.readline()
                frame = []
                for symbol in expected:
                    row = stream.readline().split()
                    if len(row) != 4 or row[0].lower() != symbol.lower():
                        raise ValueError('IRC trajectory atom identities/order differ from the output, or a frame is incomplete.')
                    frame.append([float(x) for x in row[1:]])
                if len(frames) >= len(reaction.energies):
                    raise ValueError('IRC trajectory has more frames than the reported path.')
                match = re.search(r'\bE\s*[:=]?\s*([-+\d.Ee]+)', comment)
                if match and not reaction.relative and abs(float(match[1])-reaction.energies[len(frames)]) > 2e-5:
                    raise ValueError('IRC trajectory energies do not match the path order.')
                frames.append(frame)
            except (ValueError, IndexError) as error:
                raise ValueError(str(error) or 'Invalid IRC trajectory.') from error
    coords = np.asarray(frames, dtype=float)
    if coords.shape != (len(reaction.energies), len(expected), 3) or not np.isfinite(coords).all():
        raise ValueError('IRC trajectory must contain one complete frame per reported path point.')
    # Preserve original calculation metadata and vibration reference geometry.
    return replace(calculation, coords=coords, energies=reaction.energies.copy() if not reaction.relative else np.full(len(coords), np.nan),
                   convergence={}, reaction_path=replace(reaction, steps=np.arange(len(coords))),
                   summary={**calculation.summary, 'IRC trajectory': Path(path).name})
