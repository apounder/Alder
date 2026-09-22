# Molecule Studio

An offline desktop application for viewing computational chemistry results,
building molecules, and exporting figures. Calculation files and structures
are processed locally.

## Features

- Gaussian and ORCA results: optimization trajectories, energies, orbital
  levels, animated vibrations, and UV–Vis spectra from reported excited states.
- IRC profiles and 1D/2D scan maps with linked geometries and path playback;
  unrestricted, CPCM/SMD solvent, and MP2 jobs.
- Multiple loaded calculations, structure overlays, rigid alignment, RMSD,
  explicit atom correspondence, individual structure colors, and adjustable playback speed.
- Gaussian/ORCA input setup with live preview and local input-file export.
- ASE/Sella `.traj`, extended XYZ, and geomeTRIC optimization XYZ trajectories,
  including saved energies and maximum forces when available.
- UV–Vis transition tables, Gaussian/Lorentzian broadening, wavelength/energy
  axes, CSV data export, and PNG/SVG/PDF plots. Tested with TDDFT/TDA, CIS,
  ADC(2), EOM-CCSD, and STEOM-CCSD outputs.
- Interactive 3D structures with shared appearance controls, atom labels,
  distance, angle, and dihedral measurements, adjustable depth-cue fog, and
  colors for all 118 elements. Familiar main-group colors are retained;
  metals use related, muted shades across all 3D views and exports.
- 2D and 3D molecule editing with SMILES input, atom substitution, ring and
  functional-group insertion, hydrogen adjustment, and undo/redo.
- Cube-field visualization, including orbitals, ESP, NCI, and IGM/IGMH.
- Dative arrows and dashed transition-state bonds in the shared 3D renderer.
- Structure export to MOL, XYZ, and PDB; Studio or ray-traced PNG/TIFF figures
  with transparent backgrounds, and WebM trajectory/vibration movies.

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

1. Use **Open files** or drag files into the window. Gaussian/ORCA outputs and
   XYZ structures open in the calculation viewer. Multi-frame XYZ, `.extxyz`, and
   `.traj` retain all frames for playback. MOL, SDF, and PDB open in **Build**.
   Use **Build → Edit geometry** to edit a copy of a viewed XYZ frame.
2. Inspect calculation steps, orbital levels, vibrations, and UV–Vis spectra in the
   results panel. Use **Build** to create or edit a molecule in 2D or 3D.
3. Load `.cube` or `.cub` files in **Surfaces** and select the surface and color
   fields. ESP, NCI, and IGM visualizations require precomputed fields.
4. Adjust the appearance in **View**. Under **Figure**, select two atoms and set
   a single, double, triple, **Dative →**, or **TS ⋯** bond, or remove it; select
   the donor first for dative arrows. These edits do not move atoms or adjust
   hydrogens. They remain in playback, comparison overlays, copied structures,
   and exported figures. The Build bond selector also supports dative and TS bonds.
5. In **Figure**, choose **Ray traced** and the sample count, then export an
   image or video. Videos can include every calculation geometry, linked IRC/scan
   points, or the selected mode from **Results → Vibrations**. Rendering is local
   and cancellable; no external video encoder is needed.

Enable **View → Fog / depth cue** to fade distant geometry into the background.
Click **Depth cue**, then an atom, to set where fading starts. With fog enabled,
right-drag empty space horizontally to move its start depth; **Shift + right-drag**
still pans. Strength and depth sliders are also available in View. Fog applies to
Studio and ray-traced images and videos; transparent exports keep their alpha.

Open multiple outputs together to enter **Compare**, or add files from that tab.
Choose the reference and a frame for each structure. Alignment uses an unweighted
proper rotation and translation; reflections are excluded. Heavy atoms are used
by default. Correspondence follows element order after filtering hydrogens;
equivalent atoms are not automatically permuted. For reordered atoms or shared
fragments, select a row and enter reference:moving pairs such as `1:3, 2:1, 3:2`.
Explicit pairs override the heavy-atom filter. RMSD is reported before and after
alignment and can be exported to CSV. **Solid color per structure** and each row's
color button style overlays, which can be exported through **Figure**. Original
coordinates are unchanged. Switch individual outputs in **Calculation**.

**Calculation setup** uses the current calculation geometry, the reference in
Compare, or the 3D builder.
It writes Gaussian `.gjf` or ORCA `.inp` files for single points, optimization,
frequencies, TS optimization, IRC, relaxed 1D/2D scans, and TDDFT/TDA. Charge,
multiplicity, method, basis, solvent, resources, and additional keywords are
editable. ORCA memory per process uses 80% of the entered total memory budget.
The app prepares inputs; running calculations requires the corresponding engine.

For MLIP-driven jobs, open the saved ASE/Sella trajectory or geomeTRIC optimization
XYZ; optimizer logs alone may lack coordinates. ASE energies are read in eV and
geomeTRIC energies in Hartree, then displayed in Hartree. Plain XYZ energies need
an explicit unit; unknown values stay blank. No ML model or calculator is executed.
Frames must have identical atom identities/order. Periodic trajectories show their
stored coordinates without periodic images or unwrapping. Orbital, frequency, and
excited-state results are available only when present in a supported output file.

Save builder work with **Export MOL** before closing; drafts are not saved
automatically. MOL preserves bond orders; XYZ does not. Generated coordinates
and **Tidy geometry** provide approximate geometry and should be reviewed
before use in calculations. Studio MOL files preserve dative direction and TS
annotations; TS uses a query bond plus a Studio-specific record that other
editors may not preserve. XYZ/PDB do not preserve these annotations. TS
contacts must be removed before conversion to a 2D chemical structure.
Calculation-view bond edits persist while that calculation is open. To retain
them between sessions, use **Build → Edit geometry → Export MOL** and reopen
that MOL file. Original calculation and XYZ files are not modified.

Ray tracing requires WebGL 2 and uses physical lighting in place of preview
outlines and screen-space ambient occlusion. Higher sample counts reduce noise
and take longer. Video exports retain the camera and molecular appearance,
have opaque backgrounds, and omit static cube fields. Mode amplitudes are
illustrative, including imaginary TS modes; trajectories include every geometry
without interpolating uncalculated structures.

UV–Vis uses the last reported transitions and electric-dipole absorption
strengths when available. Broadening widths are in eV; the curve is a calculated
spectrum, not experimental absorbance. The geometry energy profile displays
SCF/DFT reference energies, including for excited-state jobs. MP/CC total
energies appear in the calculation summary when reported.
**IRC / Scans** shows reported path points; missing grid points stay blank.
For ORCA IRC geometry playback, keep `_IRC_Full_trj.xyz` beside its output,
or use **Attach IRC trajectory**. Geometry links require matching atoms and
frame counts; printed trajectory energies are checked when present.

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
