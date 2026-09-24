"""Electronic transitions and oscillator-strength broadening (no GUI dependency)."""
from dataclasses import dataclass

import numpy as np
from cclib.parser.utils import convertor


@dataclass
class ElectronicTransitions:
    energies: np.ndarray  # eV; sorted by energy, not program-specific state number
    strengths: np.ndarray  # dimensionless oscillator strengths; NaN = not reported
    symmetries: list
    method: str
    source: str

    def positions(self, unit):
        if unit == 'eV':
            return self.energies.copy()
        if unit == 'cm⁻¹':
            return convertor(self.energies, 'eV', 'wavenumber')
        if unit == 'nm':
            return wavelength(self.energies)
        raise ValueError(f'Unsupported spectrum unit: {unit}')


def wavelength(energies):
    energies = np.asarray(energies, dtype=float)
    result = np.full(energies.shape, np.nan)
    valid = np.isfinite(energies) & (energies > 0)
    result[valid] = 1e7 / convertor(energies[valid], 'eV', 'wavenumber')
    return result


def read_transitions(data, warnings):
    """Use length-gauge absorption, never an unrelated SOC/combined spectrum.

    In the pinned cclib build, etenergies is converted to cm^-1 on return,
    but ORCA transprop energies remain in Hartree. Its tables also retain
    their printed order, while etenergies/etsyms have been energy-sorted.
    """
    reported = np.asarray(getattr(data, 'etenergies', []), dtype=float)
    energies = reported
    strengths = np.asarray(getattr(data, 'etoscs', []), dtype=float)
    source = 'Reported electronic transitions'
    spectra = getattr(data, 'transprop', {})
    key = 'ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS'
    if key in spectra:
        raw, strengths = spectra[key]
        energies = convertor(np.asarray(raw, dtype=float), 'hartree', 'wavenumber')
        strengths = np.asarray(strengths, dtype=float)
        source = 'Electric-dipole absorption (length gauge)'
    elif spectra:
        # Other tables can overwrite cclib's etoscs. Do not label multipole
        # intensities or emission strengths as electric-dipole UV absorption.
        strengths = np.empty(0)
        warnings.append('No electric-dipole absorption table found; UV oscillator strengths are unavailable.')
    if energies.ndim != 1 or not len(energies):
        return None
    if strengths.shape != energies.shape:
        strengths = np.full(energies.shape, np.nan)
        warnings.append('Incomplete oscillator-strength table; intensities remain blank rather than being assigned to different states.')
    order = np.argsort(energies, kind='stable')
    energies, strengths = energies[order], strengths[order]
    symmetries = [''] * len(energies)
    syms = getattr(data, 'etsyms', [])
    # Matching sorted arrays preserves degeneracies without nearest-neighbor
    # reassignment. The tolerance covers printed ORCA energy rounding.
    if reported.shape == energies.shape and len(syms) == len(energies):
        indices = np.argsort(reported, kind='stable')
        if np.allclose(reported[indices], energies, rtol=1e-5, atol=.15):
            symmetries = [str(syms[i]) for i in indices]
    if np.any(~np.isfinite(energies) | (energies <= 0)):
        warnings.append('Nonpositive or invalid excitation energies cannot be plotted as UV–Vis absorption.')
    if np.any(np.isfinite(strengths) & (strengths < 0)):
        warnings.append('Negative oscillator strengths were reported; their signs are preserved in the UV–Vis plot.')
    return ElectronicTransitions(convertor(energies, 'wavenumber', 'eV'), strengths, symmetries,
                                 data.metadata.get('excited_states_method', 'Excited states'), source)


def broaden(transitions, fwhm=.3, shape='Gaussian', unit='nm', points=2400):
    """Area-normalized lines in energy space, re-labelled on the chosen axis.

    The ordinate remains oscillator-strength density per eV, including on a
    wavelength axis (no Jacobian). It is not experimental absorbance.
    Missing intensities are omitted; a reported zero stays zero.
    """
    if not np.isfinite(fwhm) or fwhm <= 0 or shape not in ('Gaussian', 'Lorentzian'):
        raise ValueError('Choose a positive FWHM and Gaussian or Lorentzian broadening.')
    e, f = transitions.energies, transitions.strengths
    valid = np.isfinite(e) & (e > 0)
    if not valid.any():
        return np.empty(0), np.empty(0)
    low = max(float(e[valid].min()) - 4*fwhm, float(e[valid].min())*.25)
    high = float(e[valid].max()) + 4*fwhm
    if unit == 'nm':
        x = np.linspace(*wavelength([high, low]), points)
        grid = convertor(1e7/x, 'wavenumber', 'eV')
    elif unit in ('eV', 'cm⁻¹'):
        grid = np.linspace(low, high, points)
        x = grid if unit == 'eV' else convertor(grid, 'eV', 'wavenumber')
    else:
        raise ValueError(f'Unsupported spectrum unit: {unit}')
    known = valid & np.isfinite(f)
    if not known.any():
        return x, np.full_like(x, np.nan)
    y = np.zeros_like(grid)
    # One line at a time bounds memory even for large excited-state tables.
    for energy, strength in zip(e[known], f[known]):
        delta = (grid - energy) / fwhm
        if shape == 'Gaussian':
            y += strength * np.sqrt(4*np.log(2)/np.pi)/fwhm * np.exp(-4*np.log(2)*delta**2)
        else:
            y += strength / (2*np.pi*fwhm) / (delta**2 + .25)
    return x, y
