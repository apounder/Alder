# Molecule Studio

An offline desktop application for viewing computational chemistry results,
building molecules, and exporting figures. Calculation files and structures
are processed locally.

## Features

- Gaussian and ORCA results: optimization trajectories, energies, orbital
  levels, and animated vibrational modes when present in the output.
- Interactive 3D structures with shared appearance controls, atom labels,
  and distance, angle, and dihedral measurements.
- 2D and 3D molecule editing with SMILES input, atom substitution, ring and
  functional-group insertion, hydrogen adjustment, and undo/redo.
- Cube-field visualization, including orbitals, ESP, NCI, and IGM/IGMH.
- Structure export to MOL, XYZ, and PDB; figure export to PNG and TIFF with
  transparent backgrounds.

## Installation

Download a platform-specific package from **Releases** when available.
Standalone packages include their dependencies and require no Python, npm,
or local server. GitHub's **Source code** archives require a source installation.

| Platform | Installation |
| --- | --- |
| Windows 10 (1809+) / 11, x64 | Run the setup executable, or extract the portable ZIP and open `MoleculeStudio.exe`. Keep the `_internal` folder beside it. |
| macOS 15+, Apple Silicon or Intel | Experimental packaging. Choose the matching DMG and drag **Molecule Studio** into **Applications**. |
| Linux | Install from source as described below. |

Windows builds are unsigned. macOS builds are not Apple-notarized, and Mac
validation is pending. Build and first-launch instructions:
[Windows](packaging/WINDOWS.md) · [macOS](packaging/MACOS.md).

## Usage

1. Use **Open files** or drag files into the window. Gaussian/ORCA outputs open
   in the calculation viewer; MOL, SDF, XYZ, and PDB structures open in **Build**.
2. Inspect calculation steps, orbital levels, and vibrational modes in the
   results panel. Use **Build** to create or edit a molecule in 2D or 3D.
3. Load `.cube` or `.cub` files in **Surfaces** and select the surface and color
   fields. ESP, NCI, and IGM visualizations require precomputed fields.
4. Adjust the appearance in **View** and export images from **Figure**.

Save builder work with **Export MOL** before closing; drafts are not saved
automatically. MOL preserves bond orders; XYZ does not. Generated coordinates
and **Tidy geometry** provide approximate geometry and should be reviewed
before use in calculations.

## Development

Requires Python 3.11+, Git, and working OpenGL/WebGL graphics. Linux also needs
the system libraries required by Qt WebEngine. From the repository root,
create and activate a virtual environment, then run:

```sh
python -m pip install ".[dev]"
molecule-studio
```

Run the Python tests with `python -m pytest -q`. Desktop integration tests in
`tests/*_smoke.py` require a graphical session.

Bundled renderer and editor assets are included in the repository. Editing
them requires Node.js; see [web development instructions](web/README.md).
Use the platform guides above to build standalone releases. Test-data
provenance and licenses are documented in [tests/data](tests/data/README.md).
