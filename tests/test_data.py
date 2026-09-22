from pathlib import Path
from dataclasses import replace

import numpy as np
import pytest

from molecule_studio.data import BOHR, Calculation, read_calculation, read_cube, register_cube, validate_mapping

DATA = Path(__file__).parent / "data"


@pytest.mark.parametrize("filename,steps,first,last", [
    ("gaussian-opt.log", 5, -382.294279146, -382.308266602),
    ("orca-opt.out", 4, -382.05510864, -382.05513337),
    ("orca6-opt.out", 4, -382.05510862, -382.05513340),
])
def test_real_optimizations(filename, steps, first, last):
    calc = read_calculation(DATA / filename)
    assert calc.coords.shape == (steps, 20, 3)
    assert calc.energies[0] == pytest.approx(first, abs=1e-8)
    assert calc.energies[-1] == pytest.approx(last, abs=1e-8)
    assert calc.summary["Optimization"] == "Converged"
    assert calc.summary["Termination"] == "Normal"
    assert not calc.warnings
    assert calc.xyz(0).splitlines()[0] == "20"
    assert 0 in calc.convergence


def test_unfinished_step_does_not_borrow_energy(tmp_path):
    text = (DATA / "gaussian-opt.log").read_text()
    cutoff = text.index(" SCF Done:", text.index(" SCF Done:") + 1)
    path = tmp_path / "unfinished.log"
    path.write_text(text[:cutoff])
    calc = read_calculation(path)
    assert len(calc.coords) == 2
    assert np.isfinite(calc.energies[0])
    assert np.isnan(calc.energies[1])
    assert calc.summary["Termination"] == "Incomplete / unknown"
    assert calc.warnings


def cube_text(angstrom=False, orbital=False):
    scale = BOHR if angstrom else 1
    n = -2 if angstrom else 2
    return ("Synthetic signed field\nFor parser tests only\n"
            f"{'-3' if orbital else '3'} 0 0 0\n"
            f"{n} {scale} 0 0\n{n} 0 {scale} 0\n{n} 0 0 {scale}\n"
            f"8 0 0 0 0\n1 0 {scale} 0 0\n1 0 0 {scale} 0\n"
            + ("1 7\n" if orbital else "") + "-1D-1 0.1 0.2 0.3 0.4 0.5 0.6 0.7\n")


@pytest.mark.parametrize("angstrom,orbital", [(False, False), (True, False), (False, True)])
def test_cube_units_and_single_orbital(tmp_path, angstrom, orbital):
    path = tmp_path / "field.cube"
    path.write_text(cube_text(angstrom, orbital))
    cube = read_cube(path)
    assert cube.coords[1, 0] == pytest.approx(BOHR)
    assert cube.minimum == -0.1
    assert cube.maximum == 0.7
    assert cube.text.splitlines()[2].split()[0] == "3"
    # Round-trip the normalized cube that is sent to the renderer.
    path.write_text(cube.text)
    assert np.allclose(read_cube(path).coords, cube.coords)


@pytest.mark.parametrize("replacement", [
    "-0.1 0.1", "nan 0.1 0.2 0.3 0.4 0.5 0.6 0.7", "1 2 3 4 5 6 7 8 9"
])
def test_invalid_cube_grid_is_rejected(tmp_path, replacement):
    path = tmp_path / "bad.cube"
    lines = cube_text().splitlines()
    lines[-1] = replacement
    path.write_text("\n".join(lines))
    with pytest.raises(ValueError, match="grid"):
        read_cube(path)


def test_registration_handles_rotation_and_hides_wrong_geometry(tmp_path):
    path = tmp_path / "field.cube"
    path.write_text(cube_text())
    cube = read_cube(path)
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    matching = cube.coords @ rotation + [3, 7, 9]
    wrong = matching.copy()
    wrong[1] += [1, 0, 0]
    calc = Calculation("test", cube.atomnos, np.array([wrong, matching]), np.array([-1., -2.]))
    step, coords, rmsd = register_cube(calc, cube)
    assert step == 1
    assert rmsd < 1e-12
    assert np.allclose(coords[1], cube.coords)
    calc.coords = calc.coords[:1]
    with pytest.raises(ValueError, match="does not match"):
        register_cube(calc, cube)
    calc.atomnos = np.array([6, 1, 1])
    with pytest.raises(ValueError, match="atoms differ"):
        register_cube(calc, cube)


def test_unrecognized_file(tmp_path):
    path = tmp_path / "other.log"
    path.write_text("not a calculation")
    with pytest.raises(ValueError, match="not recognized"):
        read_calculation(path)


def test_mapped_fields_require_same_geometry_and_grid(tmp_path):
    path = tmp_path / "density.cube"
    path.write_text(cube_text())
    surface = read_cube(path)
    path.write_text(cube_text(angstrom=True))
    color = read_cube(path)
    validate_mapping(surface, color)  # Equivalent grids expressed in different units.
    for mismatched in [replace(color, origin=color.origin + 0.1),
                       replace(color, axes=color.axes * 1.1),
                       replace(color, dimensions=(3, 2, 2))]:
        with pytest.raises(ValueError, match="different grids"):
            validate_mapping(surface, mismatched)
    with pytest.raises(ValueError, match="same atoms"):
        validate_mapping(surface, replace(color, coords=color.coords + 1))


def test_orbital_and_vibration_data_match_real_outputs():
    from cclib.io import ccread
    for name in ('gaussian-freq.log', 'orca-freq.out'):
        path=Path(__file__).parent/'data'/name
        parsed=read_calculation(path)
        raw=ccread(str(path))
        np.testing.assert_allclose(parsed.frequencies,raw.vibfreqs)
        np.testing.assert_allclose(parsed.ir_intensities,raw.vibirs)
        np.testing.assert_allclose(parsed.displacements,raw.vibdisps)
        np.testing.assert_allclose(parsed.vibration_coords,raw.atomcoords[-1])
        np.testing.assert_allclose(parsed.orbitals[0]['energies'],raw.moenergies[0])
        assert parsed.orbitals[0]['homo']==raw.homos[0]==34
        assert len(parsed.frequencies)==54
        assert parsed.displacements.shape==(54,20,3)
    missing=read_calculation(Path(__file__).parent/'data/gaussian-opt.log')
    assert len(missing.frequencies)==0 and missing.displacements is None


def test_unrestricted_orbital_channels():
    calc=read_calculation(Path(__file__).parent/'data/gaussian-unrestricted.log')
    assert [(c['spin'],c['homo'],len(c['energies'])) for c in calc.orbitals]==[('Alpha',34,60),('Beta',33,60)]
    assert not np.array_equal(calc.orbitals[0]['energies'],calc.orbitals[1]['energies'])
