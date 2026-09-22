# Molecule Studio

A standalone desktop viewer for Gaussian and ORCA output, optimization
trajectories, energies, ESP/NCI/IGM surfaces, high-resolution figures, and an integrated molecule builder. Files are read locally. The 3D
renderer is bundled; using the application does not require a network connection.

## Windows download

The initial Windows x64 installer and portable ZIP have been built and checked
on Windows 11 ARM64 using x64 emulation. Local builds are written to
`dist/release`; the GitHub workflow produces the same download formats.

Once a build is published, download **MoleculeStudio-0.2.0-Windows-x64-Setup.exe**
from the repository's **Releases**, double-click it, and follow the installer.
Open **Molecule Studio** from the Start menu. No terminal, Python, npm, or local
server is needed. All editors and chemistry/rendering assets are included.

Alternatively, download the **Portable.zip**, choose **Extract All**, open the
extracted `MoleculeStudio` folder, and double-click `MoleculeStudio.exe`. Keep
its `_internal` folder alongside it. Downloading GitHub's **Source code.zip**
does not give you a runnable Windows application.

The target is 64-bit Windows 10 (1809+) / Windows 11 with working graphics
drivers. Native Intel/AMD Windows and Windows 10 still need independent checks.
Initial builds are unsigned, so Windows may show an unknown-publisher warning.

To produce and publish the download using GitHub's website, see
[Windows release instructions](packaging/WINDOWS.md).

## Run in this workspace

```bash
cd /home/austin/molecule-studio
./launch.sh --software
```

The software option is for this container's virtual display. On a regular Linux
desktop with working GPU drivers, use `./launch.sh` without that option.
You can also pass a calculation and a cube as command-line arguments:

```bash
./launch.sh --software tests/data/gaussian-opt.log
```

## Workflow

1. Drop a Gaussian `.log` or ORCA `.out` file anywhere in the window, or use
   **Open files**. Other filename extensions work through **All files**.
2. The final available geometry opens first. Drag the step slider, click the
   energy plot, select a row in **Step data**, or press **Play** to follow the
   optimization trajectory.
3. Inspect the program, method/basis when reported, charge/multiplicity,
   termination and optimization status. Thermochemical energies, temperature,
   imaginary-frequency count, and final MP/CC energies appear when parsed.
4. The linked plot shows **SCF/DFT electronic energy**, with absolute or relative
   values in Hartree, kcal/mol, or kJ/mol. The selected geometry always shows its
   absolute SCF/DFT energy in Hartree. Available optimization convergence values
   are shown as `value / threshold` in atomic units.
5. Drop a `.cube` or `.cub` file. The app checks atom identities and ordering,
   finds the best matching geometry, and aligns the trajectory to the cube's
   coordinate frame. In **Surfaces**, adjust **Isovalue**, **Opacity**, and
   **Positive + negative lobes**.
   Positive surfaces are blue; negative surfaces are orange. Isovalues use the
   scalar field's native units.
6. A surface is shown only at its associated geometry. Moving to a different
   step hides it; returning restores it. Additional cubes are retained in the
   surface/color field dropdowns. Choose the roles explicitly when filenames
   are ambiguous (such as Multiwfn's `func1.cub` / `func2.cub`).
7. **Figure** selects appearance and export settings. **Export figure** renders
   the current view to PNG or TIFF at the requested pixel size.
   **Step data** also offers energy CSV and selected-geometry XYZ exports. XYZ
   exports preserve the original parsed coordinates.

You can drop the output and cube together; the output loads first. Opening a
cube alone displays its atoms and field without inventing calculation energies.
The real Gaussian 16 and ORCA 5/6 files in `tests/data` are usable examples.

## Build molecules in Studio

The **Build** inspector integrates the atom-by-atom editor into Studio's native
layout. Everything, including RDKit's JavaScript/WASM runtime, is bundled and
runs offline. Running the desktop app does not require npm, Node.js, localhost,
or the separate web app.

- The **2D / 3D** switch opens a local Ketcher line-drawing editor or Studio's
  spatial editor. The Rowan-inspired Build layout places compact tools on the
  right, with rectangle/lasso selection and rotation of selected atoms in 3D.
- Switching to 2D generates a drawing without changing existing 3D coordinates.
  **Convert to 3D** applies the sketch using local RDKit ETKDG and MMFF94/UFF,
  preserving specified stereochemistry and creating an undo checkpoint.
  Unapplied 2D edits survive switching back to 3D. Conversion is limited to 300
  heavy atoms and runs in a background thread. Save drawings as MOL, PNG, or SVG.
- Expand **SMILES and sample molecules** to paste a SMILES string or choose a sample.
- **Edit geometry** copies the currently selected calculation step into an
  editable draft, in the coordinate frame currently being viewed. Its inferred
  bonds start as single bonds and can be edited. The original coordinates,
  trajectory, energies, and cube fields are retained.
- Choose an element from the palette or full periodic table, then click an atom
  to **replace** it. Choosing an element activates **Replace atom** automatically.
  Existing bonds remain, and automatic hydrogen adjustment adds or removes H as
  needed. For example, replacing a terminal carbon of ethane with O makes methanol.
  **Apply element to selection** performs the same substitution on selected atoms.
- **New molecule** starts a blank draft in **Replace atom**; click empty space to
  place an atom. To extend a structure, choose an element and then **Attach atom**.
  Click an atom to attach the new element, or drag to grow a bond/connect atoms.
  In either tool, clicking an existing bond applies the selected single/double/triple order.
- **Adjust hydrogens when editing** fills neutral main-group valences. Place C
  to make methane, click H with C selected to make ethane, then replace another
  H with O to make ethanol. Charged atoms and metals require manual editing.
  Disable adjustment for radicals/unusual valences. **Complete hydrogens** is
  also available as an explicit, undoable operation.
- In Replace atom, right-click an atom/bond to delete it; left/middle-drag rotates and
  right-drag pans. Erasing H deliberately leaves the open valence until the
  next hydrogen adjustment. Scroll zooms in every tool.
- **Select** two, three, or four atoms to measure distance, angle, or dihedral.
  Shift-click builds a larger selection for group movement; measurements are
  hidden for groups larger than four. **Move** drags the selection in the view
  plane. **Erase** removes atoms or individual bonds. **Attach atom** grows an atom
  on click, connects atoms on drag, or applies the chosen order to a bond. **Apply element** changes the
  selection. Valence warnings allow the edit.
- **Rings / groups** opens 44 prepared fragments: saturated/aromatic rings,
  heterocycles, alkyl chains, esters, amides, carbonyl groups, ethers, nitrile,
  nitro, and more. Click a numbered atom in the small diagram (or use **Join at**)
  to choose the green joining atom. Ester entries distinguish the carbonyl and
  oxygen sides. Hover over the molecule for a translucent 3D placement preview.
- In **Replace atom · share junction**, click an atom to replace it with the
  highlighted fragment atom, preserving the existing external bonds. Replacing
  a cyclohexane carbon with cyclopentane gives a spiro[4.5] junction; replacing a
  terminal carbon with Ethyl extends the chain. Hydrogens adjust at the junction.
- **Attach group · add a bond** connects the fragment by a new single bond;
  clicking a terminal H substitutes it. **Replace selected / Attach to selected**
  applies to exactly one selected atom. **Place separately**, or clicking empty
  space, inserts a disconnected fragment. Every insertion is one undo step;
  ambiguous multi-atom selections cannot silently create a disconnected group.
  In both modes, excess joining hydrogens are removed even with **Adjust
  hydrogens when editing** off; unrelated manual hydrogen edits are preserved.
- Fragment coordinates and numbered depictions are bundled, with no WASM wait
  or network access on insertion. Placement preserves the fragment geometry and
  rotates it to reduce clashes; it does not optimize the assembled molecule.
- **View**, above the canvas, controls every 3D workspace: Studio / Paton-inspired /
  Soft studio presets, outlines, ambient occlusion, projection, hydrogens, labels,
  atom size, background, and explicit auto-rotate. Calculation, Figure, and Build
  use the same Three.js renderer and the same settings.
- Free trackball rotation passes continuously through both poles without an up-axis lock.
  Camera movement has no momentum. Rendering stops when idle and when a 3D view
  is hidden; frames are requested for interactions, edits, playback, and enabled
  auto-rotate. Playback reuses GPU buffers when connectivity is unchanged.
- **Undo/Redo** retain 50 edit snapshots, including replaced/imported drafts.
  **Tidy geometry** relaxes bond lengths and clashes; it is undoable.
- With the building canvas focused, use `1/V`, `2/A`, `3/M`, `4/D`, `5/B` for
  Select/Replace atom/Move/Erase/Attach atom, `Ctrl+Z` and `Ctrl+Shift+Z` for undo/redo,
  `9/G` for fragments, `Delete` for the selection, and `Esc` to return to Select.
- **Open files** and drag/drop accept MOL V2000, SDF, XYZ, and PDB structures;
  these open in Build. Only the first SDF record and PDB model are imported.
  XYZ/PDB without connectivity infer single bonds. Export **XYZ**, **MOL**,
  or **PDB** from Build; MOL preserves explicit bond orders.
- **Preview figure in Studio**, or the **Figure** tab while working on a draft,
  keeps the same rendered scene, bond orders, and camera orientation, hiding
  editing overlays. PNG/TIFF exports use that scene at the requested resolution.
  The header's **Export figure** opens this preview when invoked from Build.
- Return to **Build** to keep editing, or **Calculation/Surfaces** to return to
  the unchanged calculated structure and its original fields. The energy plot
  and optimization timeline are hidden while viewing a draft: edits have no
  computed energy, and calculated cube surfaces are not attached to them.

SMILES fallback coordinates are approximate and Tidy is not a force-field
optimizer; inspect the geometry before scientific use. Drafts are retained while
switching inspectors, but are not automatically saved across application exits.
Export MOL to save your work.

The builder's source adapter is `web/src/studio.js`; it reuses the
same renderer, chemistry, editor, undo, and file modules as the standalone web
app. Developers regenerate the bundled desktop asset with
`node scripts/package-studio.mjs` from `web` after installing its
build dependencies. End users only need the desktop app and its bundled assets.

## ESP, NCI, IGM, and other scalar fields

Select the analysis in **Surfaces**, then select the two cube roles:

| Analysis | Surface field | Color field | Initial isovalue |
|---|---|---|---|
| Orbital / signed field | Orbital or signed scalar cube | None | ±0.03 |
| Electron density | Electron-density cube | None | 0.002 |
| ESP on electron density | Electron-density cube | ESP cube | 0.002 |
| ESP on van der Waals | ESP cube (defines coordinates and colors) | Same cube automatically | Atomic vdW radii |
| NCI | Reduced density gradient (RDG) cube | sign(λ₂)ρ cube | 0.5 |
| IGM / IGMH | δg, δg_inter, or δg_intra cube | sign(λ₂)ρ cube | 0.005 |
| Custom mapped surface | Any scalar cube, including other interaction indicators | Another scalar cube | 0.01 |

These isovalues are editable starting points, not universal scientific settings.
The app visualizes precomputed fields; it does not derive ESP, NCI, or IGM from
an output log. For NCI, supply a suitably density-masked RDG field from your
analysis program; this viewer does not impose a density cutoff itself.

ESP uses a red–white–blue scale (negative to positive). NCI/IGM uses
blue–green–red with green at zero. The editable minimum/maximum and optional
color legend apply to both the view and exported image. Color interpolation is
trilinear. Both cubes must have the same atoms, orientation, origin, voxel axes,
and dimensions; mismatches are explained rather than silently overlaid.

For NCIPLOT's `*-dens.cube`, explicitly choose **NCIPLOT signed density ×100**
under **Input scaling**. This divides the input values by 100 before mapping,
so limits such as −0.05 to +0.05 are in atomic units. Other tools may use native
atomic units; check their output conventions. See the
[NCIPLOT manual](https://www.lct.jussieu.fr/pagesperso/contrera/NCIPLOT4_MANUAL.pdf).
Out-of-grid mapped values are shown in gray; export a grid covering the whole
surface, particularly when using ESP on van der Waals radii.

## Figure styling and export

The UI takes cues from [Rowan's public site](https://www.rowansci.com/): a green
accent, neutral panels, compact controls, and a large white molecular canvas.
Calculation, Surfaces, Figure, and Build inspectors share one workspace.

**Paton-inspired** follows numerical proportions and colors from
[Robert Paton's published PyMOL styling script](https://gist.github.com/bobbypaton/1cdc4784f3fc8374467bae5eb410edef):
0.07 Å black sticks, sphere scale 0.18 (0.13 for H), light gray carbon,
near-white hydrogen, slate-colored nitrogen, and a white background with fine
outlines. Common-element Bondi radii are used for these spheres. This is a
WebGL approximation, not an official Paton preset or a PyMOL ray-traced render.
The **Soft studio** preset enables ambient occlusion; outlines and projection
are also independently adjustable.

Exports preserve the camera and viewport aspect ratio. Set the longest edge
(400–6000 px), antialiasing, print DPI, and background in **Figure**. With 2×
supersampling, the scene is rendered at twice the final width and height and
then downsampled. DPI is print metadata; pixel dimensions determine detail.
PNG and LZW-compressed TIFF preserve alpha. An optional color scale is included
in mapped-surface exports. The GPU limit and a 24-megapixel intermediate-render
limit are checked; reduce size or use native resolution if exceeded. Final
surface detail still depends on the input cube's grid resolution.

## Scientific scope and limits

- This is a first working viewer, not a complete CYLview replacement.
- The linked energy trace is SCF/DFT, including dispersion corrections applied
  by cclib. It is not a Gibbs-energy trajectory or a correlated MP/CC energy
  trajectory. Thermochemistry in the sidebar describes the parsed job's
  reported thermochemical result, not each selected optimization step.
- An optimization trajectory is a sequence of optimizer geometries, not a
  physical-time trajectory or an IRC by implication. Separate multi-job files
  into individual calculations before comparing energies from different methods.
- Energies are associated with geometries while parsing, rather than blindly
  pairing arrays by length. Missing values remain blank, and incomplete
  termination is flagged. Some severely truncated files cannot be parsed.
- Cube matching requires identical atom order and a best-fit RMSD no greater
  than 0.020 Å. Atom permutations and multi-orbital/multi-dataset cubes are not
  supported. Export one scalar field per cube. Positive Bohr and negative-count
  ångström grids and single-orbital Gaussian cubes are supported.
- A cube supplies the field; this application does not compute orbitals from
  an output file or calculate interaction energies from surface colors.
- One calculation and up to eight cube fields can be loaded. One surface
  representation (optionally colored by a second field) is shown at a time.
  File size is limited to
  256 MiB and cube grids to 8 million values. Cube parsing runs in a background
  thread; surface meshing may briefly pause the 3D view for large grids.
- Calculation bonds are inferred for display. Builder drafts retain editable
  bond orders. Publication annotation tools and session saving are not included.

## Install from source

Python 3.11 or newer and Git are required for a source installation. Linux also
needs the usual Qt WebEngine/X11 graphics libraries. A working OpenGL/WebGL
implementation is required for the 3D view.

```bash
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows instead: .venv\Scripts\activate
python -m pip install .
molecule-studio
```

The application has been exercised on Linux and Windows 11 ARM64 (x64 emulation).
The Windows workflow builds and checks a standalone bundle and installer on a
native x64 runner. macOS packaging is not included yet.

## Dependencies and validation

- PySide6 provides the desktop UI and embedded WebEngine.
- cclib parses calculations. The dependency is pinned to upstream commit
  `f90be37ffa1ab4cfec97495bdd01d670ca329f17` because released cclib 1.8.1 failed
  on the ORCA 6 fixture's symmetry section. Git is needed during installation,
  not while using the app.
- Three.js provides the shared 3D renderer. Bundled 3Dmol.js 2.5.5 is used only
  for cube parsing and CPU surface meshing, with its license retained.
- Ketcher 3.18.0 and its Indigo worker are bundled for offline 2D drawing.
  Native RDKit 2026.3.6 performs local stereochemistry-aware conversion.
- NumPy handles coordinate alignment; Matplotlib draws the linked energy plot;
  Pillow writes PNG/TIFF files with print-resolution metadata.

```bash
.venv/bin/python -m pytest -q
# On a desktop with normal graphics libraries:
.venv/bin/python tests/gui_smoke.py /tmp/molecule-studio-preview.png
```

The parser tests use real Gaussian 16 and ORCA 5/6 optimization outputs and
exercise incomplete calculations, cube units and validation, and rigid
alignment and matched-grid validation. The GUI smoke check uses native file
drops, playback, synthetic signed/mapped fields, ESP/NCI/IGM color mapping,
trilinear sampling, NCIPLOT scaling, mismatch/recovery, Paton appearance,
supersampled transparent PNG/TIFF export, and van der Waals ESP. Fixture provenance and licensing
are recorded in `tests/data/README.md`.

### Builder integration verification

`tests/builder_smoke.py` runs the actual Qt application: a calculation geometry
is copied into Build, SMILES is rendered offline, native pointer and keyboard
editing, hydrogen completion, fragment attachment, and shared appearance are exercised; bond orders are preserved in Studio's figure renderer,
and a transparent supersampled PNG is exported. It verifies the original
calculation/energies and cube surfaces survive round trips through the builder.
Run with the same desktop environment as `tests/gui_smoke.py`.

`tests/rendering_smoke.py` checks all shared presets and representations, camera
continuity, zero idle frames, suspended hidden-view spin, and alpha exports with
ambient occlusion. `tests/sketch_smoke.py` checks offline 2D loading, conversion,
undo, and MOL/PNG/SVG exports. Developer changes to the sketch adapter are bundled
with `npm run package:sketch` in `web`; runtime still needs no npm.

## Orbital levels and vibrations

The results panel below the canvas has **Energy profile**, **Step data**,
**Orbital levels**, and **Vibrations** tabs. Orbital levels show the last printed
MO energies, HOMO/LUMO labels and gaps, and separate alpha/beta channels for
unrestricted calculations. The diagram defaults to frontier levels; All levels
shows the full range. Units can be switched between eV and Eh. These reported MO
levels are not assigned to every optimization frame.

For frequency outputs, select a row or a spectrum peak and press **Play mode**.
The frequency table includes IR intensities and Raman activities when present.
Amplitude sets the largest atom displacement; speed is visual cycles per second,
not a physical time scale. Negative frequencies are labeled imaginary, and their
oscillation is illustrative. Pause holds the displayed pose; Reset position
restores equilibrium. Missing displacement vectors disable animation without
hiding available frequency data. Both tables export CSV.

Animation runs locally in the renderer and reuses the existing atom/bond buffers.
It never changes the parsed geometry or mode vectors. Static cube surfaces are
hidden during a mode preview; leaving Vibrations restores the calculation view.
Cube-frame registration rotates the vibration vectors with the geometry.
`tests/results_smoke.py` covers real Gaussian/ORCA spectra and animation,
click-to-grow, rotation through both poles, pause/reset, and exact undo.

`tests/fragments_smoke.py` checks native fragment previews, selectable joining
atoms, both ester attachment directions, spiro topology, chain replacement,
C–H substitution with automatic hydrogen adjustment on/off, exact undo/redo,
and MOL export. Developers can regenerate the prepared library
with `.venv/bin/python scripts/build_fragments.py`; installed users do not need
this build step. The library uses the existing local RDKit ETKDG/MMFF pipeline.
