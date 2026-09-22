from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from cclib.parser.utils import convertor

from molecule_studio.data import read_calculation
from molecule_studio.spectra import ElectronicTransitions, read_transitions, broaden, wavelength

DATA = Path(__file__).parent / 'data'


@pytest.mark.parametrize('name,method,count,first_ev,first_f', [
    ('gaussian-td.log', 'TD-DFT', 5, 5.3351, .1707),
    ('gaussian-cis.log', 'CIS', 10, 10.1773, 0),
    ('gaussian-eomccsd.log', 'EOM-CCSD', 10, 3.0322, 0),
    ('orca-td.out', 'TDA', 10, 3.129485, 0),
    ('orca6-td.out', 'TDA', 10, 3.129277, 0),
    ('orca-adc2.out', 'ADC(2)', 2, 5.5541, .001205461),
    ('orca6-adc2.out', 'ADC(2)', 2, 5.5541, .001260182),
    ('orca-eomccsd.out', 'EOM-CCSD', 2, 5.4718, .000528272),
    ('orca6-eomccsd.out', 'EOM-CCSD', 2, 5.4718, .000528270),
    ('orca6-steom.out', 'STEOM-CCSD', 2, 4.6164, .000595105),
])
def test_real_excited_jobs(name, method, count, first_ev, first_f):
    calc = read_calculation(DATA / name)
    t = calc.transitions
    assert t.method == method and len(t.energies) == count
    assert t.energies[0] == pytest.approx(first_ev, abs=5e-5)
    assert t.strengths[0] == pytest.approx(first_f, abs=1e-10)
    assert len(t.symmetries) == count and all(t.symmetries)
    assert np.all(np.diff(t.energies) >= 0)
    assert calc.coords.shape[0] == 1 and np.isfinite(calc.energies).all()
    assert not calc.warnings
    assert calc.summary['Termination'] == 'Normal'
    x, y = broaden(t)
    assert np.all(np.diff(x) > 0) and np.isfinite(y).all() and y.max() > 0


def test_orca_sorting_and_units_do_not_move_triplet_strengths():
    for name in ('orca-td.out', 'orca6-td.out'):
        t = read_calculation(DATA / name).transitions
        assert all(s.startswith('Triplet') for s in t.symmetries[:5])
        np.testing.assert_array_equal(t.strengths[:5], np.zeros(5))
        assert t.symmetries[6] == 'Singlet-Bu'
        assert t.strengths[6] == pytest.approx(1.171, abs=.0001)
        assert t.positions('nm')[6] == pytest.approx(216.3, abs=.1)
    t = read_calculation(DATA / 'gaussian-td.log').transitions
    assert t.positions('nm')[0] == pytest.approx(232.39, abs=.01)
    assert t.positions('cm⁻¹')[0] == pytest.approx(43030.485, abs=.01)


def test_large_orca_excited_state_table():
    calc = read_calculation(DATA / 'orca-large-td.out')
    assert calc.coords.shape == (1, 98, 3)
    assert len(calc.transitions.energies) == 20 and calc.transitions.method == 'TDA'
    assert not calc.warnings and np.isfinite(broaden(calc.transitions)[1]).all()


@pytest.mark.parametrize('name,steps', [('gaussian-mp2.log', 1), ('orca6-mp2.out', 1),
                                      ('gaussian-scan.log', 13), ('orca6-scan.out', 12)])
def test_other_job_types(name, steps):
    calc = read_calculation(DATA / name)
    assert len(calc.coords) == steps and np.isfinite(calc.energies).all()
    assert calc.transitions is None
    assert calc.summary['Termination'] == 'Normal'
    if 'scan' in name:
        assert int(calc.summary['Scan points']) == steps
    else:
        assert float(calc.summary['Final MP energy / Eh']) < calc.energies[0]


def test_repeated_and_unfinished_gaussian_tables(tmp_path):
    text = (DATA / 'gaussian-td.log').read_text()
    start = text.index(' Excited State   1:')
    second = text.index(' Excited State   2:', start)
    # A subsequent partial excitation calculation must not inherit the old
    # four higher states or their intensities. Retain the incomplete warning.
    path = tmp_path / 'repeated.log'
    path.write_text(text[:text.index(' Normal termination')] + '\n' +
                    text[start:second].replace('5.3351 eV', '4.3351 eV').replace('f=0.1707', 'f=0.1234'))
    calc = read_calculation(path)
    assert len(calc.transitions.energies) == 1
    assert calc.transitions.energies[0] == pytest.approx(4.3351)
    assert calc.transitions.strengths[0] == pytest.approx(.1234)
    assert calc.summary['Termination'] == 'Incomplete / unknown'


def test_missing_zero_and_negative_intensities_remain_distinct():
    data = SimpleNamespace(etenergies=[20000, 30000], etoscs=[.5], etsyms=['Singlet', 'Triplet'], metadata={})
    warnings = []
    t = read_transitions(data, warnings)
    assert np.isnan(t.strengths).all() and warnings
    assert np.isnan(broaden(t)[1]).all()
    data.etoscs = [0, 0]
    t = read_transitions(data, [])
    assert np.count_nonzero(broaden(t)[1]) == 0
    data.etoscs = [-.1, .2]
    warnings = []
    t = read_transitions(data, warnings)
    assert t.strengths[0] == -.1 and broaden(t)[1].min() < 0 and warnings
    data.etenergies = [-1, 0]
    assert np.isnan(read_transitions(data, []).positions('nm')).all()
    assert not len(broaden(read_transitions(data, []))[0])


def test_prefer_electric_absorption_over_combined_or_soc_results():
    data = SimpleNamespace(etenergies=[20000, 30000], etoscs=[9, 10], etsyms=['Singlet', 'Triplet'], metadata={},
        transprop={'ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS':
            (convertor(np.array([30000., 20000.]), 'wavenumber', 'hartree'), [0, .2])})
    t = read_transitions(data, [])
    np.testing.assert_allclose(t.strengths, [.2, 0])
    assert t.symmetries == ['Singlet', 'Triplet']
    data.transprop = {'SOC CORRECTED ABSORPTION SPECTRUM': ([1, 2], [9, 10])}
    assert np.isnan(read_transitions(data, []).strengths).all()


@pytest.mark.parametrize('shape', ['Gaussian', 'Lorentzian'])
def test_broadening_width_area_and_peak_conversion(shape):
    t = ElectronicTransitions(np.array([5.]), np.array([.4]), ['Singlet'], 'test', 'test')
    x, y = broaden(t, .3, shape, 'eV', points=12001)
    peak = np.argmax(y)
    assert x[peak] == pytest.approx(5, abs=.001)
    half = np.flatnonzero(y >= y.max()/2)
    assert x[half[-1]]-x[half[0]] == pytest.approx(.3, abs=.001)
    assert np.trapezoid(y, x) == pytest.approx(.4 if shape == 'Gaussian' else .4*2/np.pi*np.arctan(8), abs=1e-5)
    nm, ynm = broaden(t, .3, shape, 'nm', points=12001)
    assert nm[np.argmax(ynm)] == pytest.approx(wavelength([5])[0], abs=.02)
    assert np.max(ynm) == pytest.approx(y.max(), rel=1e-5)
