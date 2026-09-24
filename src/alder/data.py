"""Calculation parsing, explicit step associations, and cube registration."""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from types import MethodType

import numpy as np
from cclib.io import ccopen
from cclib.parser.utils import PeriodicTable, convertor
from .spectra import ElectronicTransitions, read_transitions
from .paths import ReactionPath, PathTracker, read_reaction_path, attach_irc_trajectory
from .alignment import rigid_fit

BOHR = 0.529177210903
ELEMENTS = PeriodicTable().element
MAX_FILE_BYTES = 256 * 1024 * 1024


@dataclass
class Calculation:
    name: str
    atomnos: np.ndarray
    coords: np.ndarray
    energies: np.ndarray  # Hartree; NaN means no associated SCF/DFT energy.
    metadata: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)
    convergence: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    orbitals: list = field(default_factory=list)  # Last reported channels; energies in eV.
    frequencies: np.ndarray = field(default_factory=lambda: np.empty(0))  # cm^-1
    ir_intensities: np.ndarray = field(default_factory=lambda: np.empty(0))  # km/mol
    raman_activities: np.ndarray = field(default_factory=lambda: np.empty(0))  # Å^4/Da
    displacements: np.ndarray | None = None  # [mode, atom, xyz], as reported by cclib
    vibration_coords: np.ndarray | None = None
    transitions: ElectronicTransitions | None = None
    reaction_path: ReactionPath | None = None

    def xyz(self, step, coords=None):
        points = self.coords[step] if coords is None else coords[step]
        rows = [str(len(self.atomnos)), f"{self.name} | geometry {step + 1}"]
        rows += [f"{ELEMENTS[int(z)]} {x:.9f} {y:.9f} {v:.9f}"
                 for z, (x, y, v) in zip(self.atomnos, points)]
        return "\n".join(rows) + "\n"


def check_file(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Choose a regular calculation or cube file.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("This version supports files up to 256 MiB.")
    return path


def read_calculation(path):
    path = check_file(path)
    parser = ccopen(str(path), loglevel=logging.ERROR)
    if parser is None or parser.__class__.__name__ not in {"Gaussian", "ORCA"}:
        if parser is not None:
            parser.inputfile.close()
        raise ValueError("This file was not recognized as Gaussian or ORCA output. For ASE/Sella, open a saved .traj or .extxyz file; for geomeTRIC, open its optimization XYZ trajectory. Optimizer text logs alone may not contain coordinates.")

    # Record associations while cclib reads the file. Zipping the final arrays
    # can silently shift energies when an unfinished step has no energy.
    energy_steps, convergence_steps = {}, {}
    extract = parser.extract
    raw_points = []
    vibration_coords = None
    path_tracker = PathTracker()

    def tracked_extract(_parser, stream, line):
        nonlocal raw_points, vibration_coords
        before = {key: len(getattr(parser, key, []))
                  for key in ("scfenergies", "geovalues")}
        before_disps = (id(getattr(parser, "vibdisps", None)), len(getattr(parser, "vibdisps", [])))
        extract(stream, line)
        points = max((getattr(parser, "atomcoords", []), getattr(parser, "inputcoords", [])), key=len)
        raw_points = points
        step = len(points) - 1
        after_disps = (id(getattr(parser, "vibdisps", None)), len(getattr(parser, "vibdisps", [])))
        if after_disps != before_disps and after_disps[1] and len(points):
            vibration_coords = np.array(points[-1], dtype=float, copy=True)
        for key, mapping in (("scfenergies", energy_steps),
                             ("geovalues", convergence_steps)):
            after = len(getattr(parser, key, []))
            if after < before[key]:
                raise ValueError("This output resets its calculation data. Open each job separately.")
            if after > before[key] and step >= 0:
                mapping[step] = after - 1
        path_tracker.observe(line, step)

    parser.extract = MethodType(tracked_extract, parser)
    after_parsing = parser.after_parsing
    def complete_geometries(_parser):
        # Gaussian sometimes stops printing standard orientation during an
        # excited-state optimization. Keep one consistent input frame instead
        # of assigning every subsequent SCF energy to the first geometry.
        standard = getattr(parser, 'atomcoords', [])
        inputs = getattr(parser, 'inputcoords', [])
        if len(inputs) > len(standard) and max(energy_steps, default=-1) >= len(standard):
            parser.atomcoords = inputs
        after_parsing()
    parser.after_parsing = MethodType(complete_geometries, parser)
    try:
        data = parser.parse()
    finally:
        # cclib otherwise relies on garbage collection; our tracking callbacks
        # retain the parser and can leave an imported file locked on Windows.
        parser.inputfile.close()
        del parser.extract
        del parser.after_parsing
    if not hasattr(data, "atomcoords") or not len(data.atomcoords):
        raise ValueError("No complete molecular geometry was found in this output.")
    coords = np.asarray(data.atomcoords, dtype=float)
    # cclib trims Gaussian's trailing orientation to the number of optimization
    # status records. Preserve a distinct, complete but not-yet-evaluated step.
    if len(raw_points) > len(coords):
        raw = np.asarray(raw_points, dtype=float)
        if (raw.shape[1:] == coords.shape[1:] and np.allclose(raw[:len(coords)], coords)
                and not np.allclose(raw[len(coords):], coords[-1], atol=1e-7, rtol=0)):
            coords = raw
    atomnos = np.asarray(data.atomnos, dtype=int)
    if (coords.shape[1:] != (len(atomnos), 3) or not np.isfinite(coords).all()
            or np.any(atomnos < 1) or np.any(atomnos >= len(ELEMENTS))):
        raise ValueError("The file has unsupported atoms or invalid coordinates.")
    values = np.asarray(getattr(data, "scfenergies", []), dtype=float)
    energies = np.full(len(coords), np.nan)
    for step, index in energy_steps.items():
        if step < len(coords) and index < len(values):
            energies[step] = convertor(values[index], "eV", "hartree")
    warnings = []
    if not np.isfinite(energies).all():
        warnings.append("Some geometries have no associated SCF/DFT energy; these remain blank.")
    if not data.metadata.get("success", False):
        warnings.append("Normal termination was not reported. Available results may be incomplete.")

    summary = {"Program": data.metadata.get("package", "Unknown"),
               "Version": data.metadata.get("package_version", "—"),
               "Method": data.metadata.get("functional") or ", ".join(dict.fromkeys(data.metadata.get("methods", []))) or "—",
               "Basis": data.metadata.get("basis_set", "—"),
               "Charge / multiplicity": f"{getattr(data, 'charge', '—')} / {getattr(data, 'mult', '—')}",
               "Termination": "Normal" if data.metadata.get("success") else "Incomplete / unknown"}
    if hasattr(data, "optdone"):
        summary["Optimization"] = "Converged" if data.optdone else "Not converged"
    if hasattr(data, "scanenergies"):
        summary["Scan points"] = str(len(data.scanenergies))
    if data.metadata.get("solvent_model"):
        summary["Solvent model"] = str(data.metadata["solvent_model"])
    if data.metadata.get("solvent_name"):
        summary["Solvent"] = str(data.metadata["solvent_name"])
    for attr, label in (("enthalpy", "Enthalpy / Eh"), ("freeenergy", "Gibbs energy / Eh"),
                        ("zpve", "Zero-point correction / Eh"), ("temperature", "Temperature / K")):
        if hasattr(data, attr):
            summary[label] = f"{getattr(data, attr):.10f}"
    for attr, label in (("mpenergies", "Final MP energy / Eh"), ("ccenergies", "Final CC energy / Eh")):
        if hasattr(data, attr):
            summary[label] = f"{convertor(np.asarray(getattr(data, attr)).flat[-1], 'eV', 'hartree'):.10f}"
    if hasattr(data, "vibfreqs"):
        summary["Imaginary frequencies"] = str(sum(data.vibfreqs < 0))
    convergence = {}
    if hasattr(data, "geovalues") and hasattr(data, "geotargets"):
        labels = (["Max force", "RMS force", "Max step", "RMS step"]
                  if summary["Program"] == "Gaussian" else
                  ["Energy change", "Max gradient", "RMS gradient", "Max step", "RMS step"])
        for step, index in convergence_steps.items():
            if step < len(coords):
                convergence[step] = list(zip(labels, data.geovalues[index], data.geotargets))
    orbitals = []
    homos = np.asarray(getattr(data, "homos", []), dtype=int)
    channels = getattr(data, "moenergies", [])
    for channel, levels in enumerate(channels):
        levels = np.asarray(levels, dtype=float)
        if levels.ndim != 1 or not len(levels):
            continue
        homo = int(homos[min(channel, len(homos)-1)]) if len(homos) else None
        if homo is not None and not -1 <= homo < len(levels):
            homo = None
        orbitals.append(dict(spin=("Restricted" if len(channels)==1 else "Alpha" if channel==0 else "Beta"),
                             energies=levels, homo=homo))
    frequencies = np.asarray(getattr(data, "vibfreqs", []), dtype=float)
    if frequencies.ndim != 1 or not np.isfinite(frequencies).all():
        warnings.append("The vibrational frequency table is incomplete or invalid.")
        frequencies = np.empty(0)
    def intensities(name):
        source = np.asarray(getattr(data, name, []), dtype=float)
        # Never shift partially printed intensity rows onto different modes.
        return source if source.shape == frequencies.shape else np.full(len(frequencies), np.nan)
    displacements = np.asarray(getattr(data, "vibdisps", []), dtype=float)
    if displacements.shape != (len(frequencies), len(atomnos), 3) or not np.isfinite(displacements).all():
        displacements = None
    if vibration_coords is None:
        vibration_coords = coords[-1].copy()
    if vibration_coords.shape != (len(atomnos), 3) or not np.isfinite(vibration_coords).all():
        displacements = None
        vibration_coords = None
    transitions = read_transitions(data, warnings)
    if transitions is not None:
        summary["Excited-state method"] = transitions.method
        summary["Electronic transitions"] = str(len(transitions.energies))
        summary["Energy profile"] = "SCF/DFT reference energies (not excited-state total energies)"
    reaction_path, companion = read_reaction_path(data, coords, energies, path_tracker, path, warnings)
    if reaction_path is not None:
        summary['Job path'] = f'{reaction_path.kind} · {len(reaction_path.energies)} points'
    calculation = Calculation(path.name, atomnos, coords, energies, data.metadata, summary, convergence, warnings,
                       orbitals, frequencies, intensities("vibirs"), intensities("vibramans"), displacements, vibration_coords, transitions, reaction_path)
    if companion is not None and companion.is_file():
        try:
            calculation = attach_irc_trajectory(calculation, check_file(companion))
        except ValueError as error:
            warnings.append(f'IRC trajectory was not attached: {error}')
    return calculation


@dataclass
class Cube:
    name: str
    text: str
    atomnos: np.ndarray
    coords: np.ndarray
    minimum: float
    maximum: float
    dimensions: tuple
    origin: np.ndarray  # Å, like coords
    axes: np.ndarray  # voxel step vectors in Å


def read_cube(path):
    path = check_file(path)
    with path.open(encoding="utf-8", errors="replace") as stream:
        comments = [stream.readline().rstrip(), stream.readline().rstrip()]
        header = stream.readline().split()
        if len(header) < 4:
            raise ValueError("Invalid cube header.")
        count = int(header[0])
        if not count or abs(count) > 100000:
            raise ValueError("Invalid cube atom count.")
        if len(header) > 4 and int(header[4]) != 1:
            raise ValueError("Multi-dataset cubes are not supported. Export one surface per file.")
        origin = np.array([float(v) for v in header[1:4]])
        axes = [stream.readline().split() for _ in range(3)]
        dims = np.array([int(row[0]) for row in axes])
        vectors = np.array([[float(v) for v in row[1:4]] for row in axes])
        if np.any(dims == 0) or not (np.all(dims > 0) or np.all(dims < 0)):
            raise ValueError("Cube grid axes must have consistent, nonzero counts.")
        size = int(np.prod(np.abs(dims).astype(object)))
        if size > 8_000_000:
            raise ValueError("This version supports cube grids up to 8 million samples.")
        atomrows = [stream.readline().split() for _ in range(abs(count))]
        atomnos = np.array([int(row[0]) for row in atomrows])
        coords = np.array([[float(v) for v in row[2:5]] for row in atomrows])
        if np.any(atomnos < 1) or np.any(atomnos >= len(ELEMENTS)):
            raise ValueError("Cube contains unsupported atomic numbers.")
        if count < 0:
            orbital = stream.readline().split()
            if len(orbital) != 2 or int(orbital[0]) != 1:
                raise ValueError("Multi-orbital cubes are not supported. Export one orbital per file.")
        raw = stream.read().replace("D", "E").replace("d", "e")
        values = np.fromstring(raw, sep=" ")
        if len(values) != size or not np.isfinite(values).all():
            raise ValueError("Cube grid is truncated, contains invalid numbers, or has extra datasets.")
        if not all(np.isfinite(a).all() for a in (coords, origin, vectors)) or abs(np.linalg.det(vectors)) < 1e-15:
            raise ValueError("Invalid cube coordinates or grid axes.")
        # Normalize to the conventional single-dataset, positive-count Bohr form.
        scale = 1 / BOHR if dims[0] < 0 else 1
        bohr_coords = coords * scale
        lines = comments + [f"{abs(count)} " + " ".join(map(str, origin * scale))]
        lines += [f"{abs(int(n))} " + " ".join(map(str, vec * scale)) for n, vec in zip(dims, vectors)]
        lines += [f"{z} 0 " + " ".join(map(str, xyz)) for z, xyz in zip(atomnos, bohr_coords)]
        return Cube(path.name, "\n".join(lines) + "\n" + raw, atomnos,
                    bohr_coords * BOHR, float(values.min()), float(values.max()),
                    tuple(abs(int(n)) for n in dims), origin * scale * BOHR,
                    vectors * scale * BOHR)


def validate_mapping(surface, color):
    """Do not color vertices with a field from a different box or orientation."""
    if (not np.array_equal(surface.atomnos, color.atomnos)
            or not np.allclose(surface.coords, color.coords, atol=0.002, rtol=0)):
        raise ValueError("The surface and color cubes must contain the same atoms in the same coordinate frame.")
    if (surface.dimensions != color.dimensions
            or not np.allclose(surface.origin, color.origin, atol=1e-5, rtol=0)
            or not np.allclose(surface.axes, color.axes, atol=1e-6, rtol=0)):
        raise ValueError("The surface and color cubes use different grids. Export both on the same grid and orientation.")


def register_cube(calculation, cube):
    """Find matching step and orient the full trajectory into the cube frame."""
    if not np.array_equal(calculation.atomnos, cube.atomnos):
        raise ValueError("Cube atoms differ from the calculation. Atom identities and order must match.")
    best = None
    for step, points in enumerate(calculation.coords):
        rotation, translation, rmsd = rigid_fit(points, cube.coords)
        if best is None or rmsd < best[0]:
            best = rmsd, step, rotation, translation
    rmsd, step, rotation, translation = best
    if rmsd > 0.02:
        raise ValueError(f"Cube does not match any geometry (best RMSD {rmsd:.3f} Å; limit 0.020 Å).")
    return step, calculation.coords @ rotation + translation, rmsd
