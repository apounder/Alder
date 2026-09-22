from pathlib import Path
import re

import numpy as np
import pytest

from molecule_studio.data import read_calculation
from molecule_studio.paths import attach_irc_trajectory, coordinate

DATA = Path(__file__).parent / 'data'


def test_gaussian_excited_optimization_keeps_input_orientations():
    calc = read_calculation(DATA / 'gaussian-eom-opt.log')
    assert calc.coords.shape == (5, 11, 3)
    np.testing.assert_allclose(calc.energies, [-243.638267925, -243.613044670, -243.595318439, -243.595625815, -243.595578342], atol=1e-9, rtol=0)
    assert calc.transitions.method == 'EOM-CCSD'
    assert np.linalg.norm(calc.coords[0]-calc.coords[-1]) > .1


def test_two_dimensional_scan_maps_only_converged_points():
    calc = read_calculation(DATA / 'gaussian-scan2d.log')
    p = calc.reaction_path
    assert p.kind == 'Scan' and p.parameters.shape == (16, 2)
    assert len(calc.coords) == 183
    np.testing.assert_array_equal(p.steps, [0, 11, 26, 57, 67, 74, 81, 95, 118, 134, 142, 150, 158, 165, 172, 182])
    np.testing.assert_allclose(p.energies, calc.energies[p.steps])
    assert np.isfinite(p.energies).all()  # Summary printed ****; recover from linked SCFs.
    for dim, name in enumerate(('R(1,24)', 'R(3,25)')):
        values, _ = coordinate(name, calc.coords, 'Gaussian')
        np.testing.assert_allclose(values[p.steps], p.parameters[:, dim], atol=2e-5)
    assert 'PCM' in calc.summary['Solvent model'] and calc.summary['Solvent'] == 'water'


def test_unconverged_scan_point_does_not_shift_later_cells(tmp_path):
    text = (DATA / 'gaussian-scan2d.log').read_text()
    text = text.replace(' Optimization completed.', ' Optimization stopped.', 1)
    path = tmp_path / 'incomplete-grid.log'
    path.write_text(text)
    p = read_calculation(path).reaction_path
    assert p.steps[0] == -1 and np.isnan(p.energies[0])
    assert p.steps[1] == 11 and p.steps[-1] == 182
    assert np.count_nonzero(p.steps >= 0) == 15


def test_orca_relaxed_scan_uses_actual_completion_records():
    calc = read_calculation(DATA / 'orca6-scan-relaxed.out')
    p = calc.reaction_path
    np.testing.assert_array_equal(p.steps, [31, 38, 45, 54, 62, 69, 76, 84, 92, 100, 107, 114])
    values, _ = coordinate('Dihedral (9,8,3,2)', calc.coords, 'ORCA')
    delta = (values[p.steps] - p.parameters[:, 0] + 180) % 360 - 180
    assert np.max(np.abs(delta)) < .001
    np.testing.assert_allclose(p.energies, calc.energies[p.steps], atol=5e-5)
    assert not calc.warnings


def test_orca_two_parameter_format(tmp_path):
    # Format mutation of a real one-dimensional output exercises both ORCA
    # scan columns, without presenting invented calculations as real fixtures.
    text = (DATA / 'orca6-scan.out').read_text()
    text = text.replace('There are 1 parameter(s)', 'There are 2 parameter(s)')
    text = re.sub(r'(^\s*D7\s*:.*$)', r'\1\n                 Q  :  1.0', text, flags=re.M)
    path = tmp_path / 'two-coordinates.out'
    path.write_text(text)
    p = read_calculation(path).reaction_path
    assert p.parameters.shape == (12, 2) and len(p.labels) == 2
    assert np.all(p.parameters[:, 1] == 1)
    assert np.all(p.steps >= 0)


@pytest.mark.parametrize('reverse', [False, True])
def test_gaussian_irc_direction_and_partial_path(tmp_path, reverse):
    source = DATA / 'gaussian-irc-path.out'
    if reverse:
        text = source.read_text().replace('FORWARD path direction', 'REVERSE path direction')
        source = tmp_path / 'reverse.out'
        source.write_text(text)
    calc = read_calculation(source)
    p = calc.reaction_path
    assert p.kind == 'IRC' and len(p.energies) == 103
    assert np.all(np.diff(p.parameters[:, 0]) > 0)
    assert p.parameters[-1 if not reverse else 0, 0] == pytest.approx(-23.17564 if reverse else 23.17564)
    np.testing.assert_allclose(p.energies, calc.energies[p.steps])
    assert calc.summary['Termination'] == 'Incomplete / unknown'
    assert np.isnan(calc.energies[-1])  # Unevaluated final frame is not an IRC point.


def test_orca_irc_summary_and_companion_trajectory(tmp_path):
    source = DATA / 'orca6-opt.out'
    original = read_calculation(source)
    output = tmp_path / 'path.out'
    # Synthetic IRC section in the documented ORCA 5/6 layout.
    summary = '\nIRC PATH SUMMARY\n----------\nAll gradients are in Eh/Bohr.\n\nStep E(Eh) dE(kcal/mol) max(|G|) RMS(G)\n'
    summary += '\n'.join(f'{i+1} {energy:.8f} 0.0 0.001 0.0001' + (' <= TS' if i == 1 else '') for i, energy in enumerate(original.energies[:3]))
    output.write_text(source.read_text() + summary + '\n\n')
    calc = read_calculation(output)
    assert calc.reaction_path.parameters[:, 0].tolist() == [-1, 0, 1]
    trajectory = tmp_path / 'path_IRC_Full_trj.xyz'
    frames = []
    for i in range(3):
        rows = original.xyz(i).splitlines()
        rows[1] = f'E {original.energies[i]:.9f}'
        frames.append('\n'.join(rows))
    trajectory.write_text('\n'.join(frames)+'\n')
    calc = read_calculation(output)  # Companion found automatically.
    assert calc.coords.shape == (3, 20, 3)
    np.testing.assert_allclose(calc.coords, original.coords[:3], atol=1e-8)
    np.testing.assert_array_equal(calc.reaction_path.steps, [0, 1, 2])
    assert calc.summary['IRC trajectory'] == trajectory.name
    trajectory.write_text('\n'.join(reversed(frames))+'\n')
    with pytest.raises(ValueError, match='energies do not match'):
        attach_irc_trajectory(calc, trajectory)


@pytest.mark.parametrize('name,model', [('gaussian-cpcm.log', 'CPCM'), ('gaussian-smd.log', 'SMD'), ('orca6-cpcm.log', 'CPCM'), ('orca6-smd.log', 'SMD')])
def test_solvent_jobs(name, model):
    calc = read_calculation(DATA / name)
    assert model in calc.summary['Solvent model']
    assert np.isfinite(calc.energies).all() and not calc.warnings


def test_orca_unrestricted_channels():
    calc = read_calculation(DATA / 'orca-unrestricted.out')
    assert [c['spin'] for c in calc.orbitals] == ['Alpha', 'Beta']
    assert calc.orbitals[0]['homo'] != calc.orbitals[1]['homo']
