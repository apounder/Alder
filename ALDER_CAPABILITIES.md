# Alder: capabilities

**Reviewed:** 22 September 2026

**Source baseline:** desktop project version `0.4.0`, including the measurement and local MLIP features.

This document describes the current source implementation. Its earlier MLIP planning sections have been replaced with the implemented workflow and verified limits. A previously built installer does not include subsequent source changes. See [MLIP setup](docs/MLIP.md) and the [model/job acceptance matrix](docs/MLIP_ACCEPTANCE.md) for the detailed calculation contract and validation status.

## 1. What the application is

Alder is a local desktop application for building molecular structures, examining computational chemistry results, comparing geometries, and producing figures and movies.

The desktop uses **Python and PySide6/Qt**, with embedded **Qt WebEngine** views for the shared Three.js 3D renderer and the Ketcher 2D editor. Python handles calculation parsing, native chemistry conversion, result tables and plots, input generation, file dialogs, and packaging. JavaScript handles interactive 3D editing, molecular rendering, measurements, and image/video rendering. Qt WebChannel connects them.

End users of a standalone package do not need npm, a terminal, an external browser, or a localhost server. Calculation files are processed locally. The bundled desktop chemistry/editor assets work offline.

The app prepares Gaussian/ORCA input files and opens their completed or partial results; it does not launch Gaussian, ORCA or geomeTRIC. **Local MLIP** executes UMA, MACE or AIMNet2 through separate calculation processes, using ASE and Sella for molecular workflows. Build coordinate generation and approximate cleanup remain separate from MLIP optimization.

## 2. Main workflows and interface

| Area | What it does |
| --- | --- |
| Calculation | Select a loaded output or trajectory, inspect calculation metadata, choose a geometry, inspect energies and convergence, and play its frames. |
| Results | Energy profile/table, orbital levels, vibrations, UV–Vis spectra, and IRC/scan results. |
| Surfaces | Load cube fields, choose surface/color data, adjust isovalues and palettes, and inspect registered surfaces. |
| Figure | Choose export settings and annotate bond appearance, then render images or calculation movies. |
| Build | Create/edit a molecule in 3D or draw it in 2D and convert it to a 3D conformer. |
| Compare | Overlay multiple loaded calculations/trajectories, align structures, calculate RMSD, and assign whole-structure colors. |
| Calculation setup | Generate and save Gaussian/ORCA input text from a chosen 3D geometry. |
| Local MLIP | Set up models/environments, queue local calculations, inspect progress/results and restart saved jobs. |
| Shared canvas controls | Representation, fit, appearance presets, labels, hydrogens, background, fog/depth cue, and measurements. |

Files can be opened through a native picker or dropped into the application. Multiple calculation outputs/trajectories can be loaded together. Structure imports into the builder are handled one file at a time.

## 3. Supported imports

| Input | Current behavior | Boundary |
| --- | --- | --- |
| Gaussian output | Reads molecular geometries and supported reported results through cclib plus Studio-specific tracking. | Requires a recognizable output with at least one complete geometry. Not every Gaussian method/version/output arrangement is guaranteed. |
| ORCA output | Same result workflow, with additional IRC and scan handling. | Some IRC geometry playback requires a companion trajectory. |
| `.xyz` | Opens a single geometry or multiple frames in Calculation. Bonds are inferred for display. | Standard XYZ has no bond orders or universal energy-unit convention. |
| `.extxyz` | Uses ASE's extended-XYZ reader; reads stored energies and forces when present. | All frames must retain the same elements in the same atom order. |
| ASE `.traj` | Reads modern ASE ULM trajectories, including saved optimizer/MLIP results. | Does not load a model or evaluate an attached calculator; legacy pickle trajectories are not used. |
| Sella results | Opens a saved ASE trajectory or compatible XYZ/extended-XYZ output. | Sella log text alone is not a dedicated import format. |
| geomeTRIC results | Opens optimization XYZ and recognizes its `Iteration … Energy …` comments as Hartree energies. | Does not execute geomeTRIC or reconstruct missing coordinates from arbitrary logs. |
| MOL | Opens a V2000 structure in Build, retaining supported bonds and atom annotations. | The 3D MOL parser does not support V3000. |
| SDF | Imports the first molecule and reports when additional records are present. | Not a multi-record molecule-library interface. |
| PDB | Reads the first structure/model; uses CONECT connectivity when present, otherwise distance inference. | Not a PDB trajectory or biomolecular simulation-preparation workflow. |
| `.cube` / `.cub` | Reads one scalar field or one orbital dataset per file. | Multiple datasets/orbitals in one cube file are rejected. |
| SMILES | Builds an approximate 3D structure through the bundled RDKit JavaScript/WASM pipeline. | Coordinate-generation details differ from native 2D-to-3D conversion; see section 9. |

### Trajectory energy and force handling

- ASE energies are normally read in eV and converted to Hartree for Studio's calculation data. Supported explicit energy-unit metadata can identify eV or Hartree values.
- geomeTRIC optimization XYZ energies are treated as Hartree.
- Plain XYZ comments need an explicit supported energy unit before the value is used.
- Missing energies remain missing, displayed as blank/unavailable rather than zero.
- Saved force arrays are reduced to the maximum atomic force magnitude for each frame. The UI reports this in eV/Å.
- Import deliberately reads saved calculator results directly; it does not call an energy evaluator.
- Periodic data is displayed as stored Cartesian coordinates. The app reports its periodic character, but does not display periodic images or unwrap trajectories.

## 4. Calculation results and analysis

### Geometry, energies, and convergence

The app provides a geometry slider, clickable energy plot and table, playback, and adjustable trajectory speed from **0.1× to 10×**. Each loaded document retains its selected geometry while switching documents.

Energy displays support Hartree, kcal/mol, and kJ/mol, with absolute values or values relative to the minimum/first available energy. Gaussian/ORCA geometry profiles use associated **SCF/DFT reference energies**. Imported saved trajectories use their stored potential energies and are labeled accordingly.

Reported summary fields can include program/version, method, basis, charge/multiplicity, termination status, optimization status, solvent, zero-point correction, enthalpy, Gibbs energy, temperature, final MP/CC energy, and imaginary-frequency count. Availability depends on the output.

Optimization convergence values and thresholds are shown when reported and associated with a geometry. Incomplete jobs can still be inspected. Missing geometry-energy associations are left blank; the parser does not simply zip unequal arrays together.

Exports include an energy CSV and the selected calculation geometry as XYZ.

### Orbital levels

- Orbital-energy table and energy-level diagram.
- Restricted or separate alpha/beta channels when reported.
- Occupied/virtual identification and HOMO/LUMO information when available.
- Energy units in eV or Hartree, with an option to show all levels.
- Selection through the table or plot and CSV export.

Orbital-energy inspection and orbital-surface visualization are separate features. Orbital shapes require an external cube file; the viewer does not calculate wavefunctions or orbitals.

### Vibrations and IR data

- Frequencies, IR intensities, and Raman activities when reported.
- IR spectrum and mode selection through the spectrum/table.
- Animation using the reported normal-mode displacement vectors.
- Play/pause, reset to equilibrium, adjustable amplitude, and visual animation speed.
- Imaginary-mode identification and illustrative TS-mode oscillation.
- Frequency/intensity CSV export and selected-mode movie export.

Animation is disabled if usable displacement vectors are missing. Its amplitude and speed are visual controls, not a molecular dynamics trajectory. The underlying calculation coordinates remain unchanged.

### Excited states and UV–Vis

The tested output families include TDDFT/TDA, CIS, ADC(2), EOM-CCSD, and STEOM-CCSD. This is support for reading reported transitions, not for executing those methods.

Available controls and outputs:

- Transition table with energy, wavelength, oscillator strength, and reported spin/symmetry information.
- Gaussian or Lorentzian broadening, with full width at half maximum specified in eV.
- Horizontal axes in nm, eV, or cm⁻¹; optional normalization and transition sticks.
- Selection through the table or spectrum.
- Transition CSV, broadened-curve CSV, and plot saving through the toolbar to PNG/SVG/PDF.

The app uses the last reported transition set and electric-dipole absorption strengths when available. Table rows are energy-sorted, not necessarily the calculation program's original state numbering. Broadening remains defined in energy space even on a wavelength axis. The curve is a calculated spectrum, not experimental absorbance.

An excited-state calculation's ordinary geometry energy profile remains the SCF/DFT reference profile; it is not a general state-resolved excited-state total-energy trajectory.

### IRC, 1D scans, and 2D scans

- IRC profiles and reported reaction coordinates.
- One-dimensional scan plots and two-dimensional scan maps.
- Tables of reported path points, coordinates, energies, and geometry associations.
- Selecting a point can display its linked geometry.
- Path energy units/reference choices and CSV export.
- Movie export of path points with confirmed geometry links.

Missing grid points remain missing. Scan points without a confirmed geometry association remain unlinked. The software does not calculate or interpolate missing structures.

For ORCA IRC results, keep the matching `_IRC_Full_trj.xyz` companion beside the output or use **Attach IRC trajectory**. Attachment validates atom identities/order, frame counts, and energies when available.

## 5. Structure comparison

Compare accepts multiple loaded outputs/trajectories and provides:

- Reference-structure selection and independent frame selection for each document.
- Per-structure visibility and whole-structure color controls.
- Element colors or a solid color for each structure, including overlays of more than two structures.
- Optional rigid alignment to the reference.
- Heavy-atom alignment/RMSD by default, or all atoms.
- Explicit atom mapping with 1-based reference:moving pairs, such as `1:3, 2:1, 3:2`.
- RMSD before and after alignment, in Å, and comparison CSV export.
- Figure export of the overlay and the shared measurement tool.

Alignment uses unweighted Kabsch fitting with a proper rotation and translation. It does not reflect structures, scale them, or automatically permute equivalent atoms. An explicit mapping can identify a common subset; the paired elements must match. Too few or collinear fitting atoms are reported because the rotation may not be unique.

Original coordinates remain intact. Displayed structures keep separate connectivity; bonds are not inferred between different overlaid molecules. Overlay movie export is not implemented.

## 6. Shared 3D viewer and measurements

Calculation, Compare, Figure, and 3D Build use the same `StudioView` renderer and appearance controls.

### Viewing and appearance

- Ball-and-stick, sticks, and space-filling representations.
- Colors for all 118 elements, retaining familiar main-group colors and using related muted colors for metals.
- Studio, Paton-inspired, and Soft studio appearance presets.
- Optional outlines and ambient occlusion in the interactive/Studio renderer.
- Orthographic or perspective projection.
- Atom-size adjustment, element labels, hydrogen visibility, and auto-rotation.
- Light, dark, and transparent/checkerboard backgrounds.
- Fit-to-structure, unrestricted trackball rotation, zoom, and pan.
- Atom hover highlights and selection overlays.

The Paton-inspired preset is a visual preset; it is not a PyMOL integration. Displaying an element does not establish that a chemistry engine, force field, or selected MLIP supports that element.

Hydrogen visibility affects display and picking, not the stored molecule. The viewer renders on demand and uses static trackball movement without an inertia animation loop. Active playback/rotation/rendering still requires computation. Atoms and bonds use instanced geometry, and compatible trajectory frames reuse GPU buffers.

### Measurements

The **Measure** control above the canvas offers:

| Mode | Pick order | Output |
| --- | --- | --- |
| Bond length | Two atoms; an existing bond is not required. | Distance in Å. |
| Angle | Three atoms, with the vertex second. | Angle in degrees. |
| Dihedral | Four ordered atoms along the torsion. | Signed angle in degrees. |

The UI shows ordered atom labels/indices and a dashed guide with a numeric label. Values update during trajectory/vibration playback and builder geometry drags. Clear or Escape clears the picks. New calculation documents clear them, while compatible trajectory frames retain them. The tool is for 3D views, not 2D drawing coordinates.

There is currently one active measurement selection per view, not a saved collection of measurement records or a measurement-versus-time plotting panel. Interactive selection/measurement overlays are hidden during molecular image exports.

### Fog and depth cue

- Fog toggle, strength slider, and start-depth slider.
- **Depth cue**, followed by clicking an atom, places the fade start at that depth.
- With fog enabled, right-dragging empty canvas adjusts its start depth.
- Shift + right-drag retains panning; with fog off, right-drag pans.
- Fog applies to Studio and ray-traced exports, including transparent images.

## 7. Cube surfaces and mapped fields

Supported surface workflows include orbitals/signed fields, electron density, ESP on an electron-density surface, ESP on a van der Waals surface, NCI, IGM/IGMH, and custom scalar-field mappings.

Users can choose separate surface and color cubes; adjust isovalue, opacity, signed lobes, color minimum/maximum, palette, and input scaling; and display/export a color legend. An NCIPLOT signed-density ×100 scaling option is available.

Studio validates atom identities, coordinate frames, and grids before combining fields. A cube can be rigidly registered to a matching calculation geometry; the displayed trajectory and vibration vectors are handled in the corresponding frame. Static surfaces are hidden at incompatible geometry steps.

These are **visualization workflows for precomputed fields**. Studio does not calculate electron density, ESP, NCI, IGM, IGMH, or orbital cubes from a structure. Multiple cubes can be loaded for field selection, but this is not a general arbitrary stack of independently configured visible surfaces.

## 8. Bond annotations and figure/movie export

### Bond appearance

Users can add/change/remove ordinary single, double, and triple bonds, directional dative arrows, and dashed TS contacts. For a dative arrow, select the donor first.

In Figure, bond annotations preserve atom coordinates and hydrogen counts. Calculation annotations persist across frames, playback, comparison overlays, copies into Build, and image/movie generation during the session. Each calculation has its own annotation state.

To save annotations between sessions, copy the geometry into Build and export MOL. Studio's MOL round trip preserves dative direction and TS annotations. TS contacts use a query-bond representation plus a Studio-specific record; another editor may not preserve that record. TS contacts must be removed before converting to a 2D chemical structure. XYZ/PDB do not preserve these annotation semantics.

### Images

- Studio rendering or local GPU path tracing.
- PNG and TIFF output, with optional true transparency and print-resolution metadata.
- Longest-edge size control, preserving the current viewport aspect ratio.
- Native or 2× supersampling for Studio images.
- Adjustable ray samples for path-traced images.
- Current molecular colors, radii, camera, bond annotations, labels, and fog.
- Progress reporting and cancellation.

Ray tracing uses physical lighting, shadows, and reflections in place of preview outlines and screen-space ambient occlusion. Quality/performance depend on sample count and graphics hardware.

### Videos

- WebM movies from a calculation's full geometry trajectory, linked IRC/scan geometries, or a selected vibrational mode, including an imaginary TS mode.
- Studio or ray-traced rendering.
- Resolution, frame-rate, frames-per-geometry, and vibration cycle controls.
- Existing camera and molecular styling are retained.
- Local encoding without a separately installed video encoder, with progress/cancellation and streamed output.

Movies have opaque backgrounds, omit static cube fields, and do not interpolate new structures between calculation frames. Export is from an individual calculation, not a Build editing session or Compare overlay. MP4/GIF export is not currently provided.

## 9. Molecular building and coordinate generation

### 3D editing

The builder supports a blank-canvas flow, structure import, SMILES, or an editable copy of a selected calculation geometry. Its tools include Select, Replace/Add atom, Move, Delete, Bond/Attach atom, rectangle selection, lasso selection, selection rotation, and fragment insertion.

- Element selection from common-element buttons or the full periodic table.
- Click an existing atom to substitute the chosen element while adjusting hydrogens when enabled.
- Apply an element to a selection.
- Place a free atom in empty space.
- Attach atoms/grow bonds, connect atoms, change bond orders, and delete atoms/bonds.
- Automatic hydrogen adjustment toggle and an explicit Complete hydrogens action.
- Valence warnings for common elements; these are not a general chemical-validity proof.
- Move/rotate selected groups; rectangle/lasso multi-selection.
- Undo/redo, with a bounded history and one undo step per completed drag.
- Tidy geometry and export to XYZ, MOL, or PDB.
- Figure preview using the same 3D renderer.

Keyboard shortcuts include numbered tools, V/A/M/D/B for common tools, R for selection rotation, G for fragments, Delete for deletion, Escape for clearing/canceling, and Ctrl+Z / Ctrl+Shift+Z for undo/redo.

### Fragment library

There are **44 prepared fragments**, with a preview diagram, selectable joining atom, and a highlighted junction. The modes are **Replace atom / share junction**, **Attach group / add a bond**, and **Place separately**. Joining hydrogens are removed to make room for the connection, including the explicit C–H substitution case. Replacement can extend chains or construct spiro junctions when the selected topology allows it.

| Category | Included entries |
| --- | --- |
| Rings | Benzene; cyclopropane, cyclobutane, cyclopentane, cyclohexane, cycloheptane, cyclooctane; cyclopentene, cyclohexene; pyridine, pyrrole, furan, thiophene, imidazole, piperidine, morpholine, tetrahydrofuran, naphthalene, indole. |
| Chains | Methyl, ethyl, propyl, isopropyl, tert-butyl, vinyl, ethynyl. |
| Functional groups | Hydroxyl, methoxy, ethoxy, amino, dimethylamino, thiol, methylthio, trifluoromethyl, nitrile, nitro. |
| Carbonyl groups | Formyl, acetyl, carboxylic acid, methyl ester and ethyl ester joined from the carbonyl side, acetoxy ester joined from oxygen, amide joined from carbonyl carbon, and acetamido joined from nitrogen. |

### 2D drawing and conversion

The embedded Ketcher editor provides atom/bond/ring drawing, charge and stereochemistry editing, undo/redo, 2D cleanup, and MOL/PNG/SVG export. Switching representations supports native RDKit 2D layout and 2D-to-3D conversion. A 2D drawing can be edited without immediately overwriting the existing 3D structure; conversion applies a new 3D model with an undo checkpoint.

Native 2D-to-3D conversion uses RDKit ETKDGv3, explicit hydrogens, chirality enforcement, and MMFF94 relaxation where parameters are available, otherwise UFF where available. Query atoms/bonds and unresolved R-groups are rejected. Failure preserves the sketch and previous 3D geometry.

### Distinguish the three existing geometry operations

| Operation | What it actually does | What it does not establish |
| --- | --- | --- |
| SMILES → 3D | Bundled RDKit JS/WASM, runtime detection of an embedding method, and a topology-based placement/relaxation fallback when needed. | Not a general native ETKDG/MMFF workflow or a calculated QM/MLIP minimum. |
| 2D → 3D | Native RDKit ETKDGv3 followed by available MMFF94/UFF relaxation. | Not a QM or MLIP calculation; no normal calculation job/result record is created. |
| Tidy geometry | A bond-length spring, nonbonded repulsion, and positional-restraint relaxer. Larger structures yield work to the animation scheduler. | Not an electronic energy, force-field energy, MLIP energy, convergence certificate, or transition-state search. |

Tidy uses up to 300 iterations by default and remains an O(N²) pairwise algorithm. Approximate coordinate generation/cleanup is separate from the MLIP optimization workflow.

## 10. Gaussian and ORCA calculation-input setup

Input setup can take the current calculation geometry, the reference geometry in Compare, or the 3D builder model. It provides a live text preview, validation, Copy input, and Save input.

| Available job | Current action |
| --- | --- |
| Single point | Generate engine input. |
| Optimization | Generate engine input. |
| Optimization + frequencies | Generate engine input. |
| Frequencies | Generate engine input. |
| Transition-state optimization | Generate engine input with the corresponding TS/frequency settings. |
| IRC | Generate engine input. |
| Relaxed 1D/2D scan | Generate one or two bond/angle/dihedral scan-coordinate rows. |
| Excited states | Generate TDDFT/TDA input with a requested number of roots. |

Settings include engine, editable method/basis, total charge, multiplicity, CPU cores, total memory, PCM/SMD solvent choices, D3(BJ), ORCA numerical frequencies/Hessian, TDA, roots, title, and additional single-line engine keywords. Defaults include common DFT/HF/MP2 methods and basis choices; editable fields do not imply that every keyword combination is supported by an installed engine.

Charge/multiplicity parity and scan indices/ranges are checked. Scan atom numbers are entered from 1; ORCA output converts them to its required indexing. ORCA `%maxcore` uses 80% of the entered total memory divided by the core count. Inputs are saved as Gaussian `.gjf` or ORCA `.inp`.

**Gaussian/ORCA setup exports input text; it does not run those engines or submit remote jobs.** The separate Local MLIP workflow has its own processes, queue, logs and recovery. The generators have been tested as text generators; they have not been validated by running every generated job through licensed Gaussian/ORCA installations.

## 11. Saving, state, and companion browser app

### Desktop persistence

- Input calculation files and original coordinates are preserved.
- Explicit exports save structures, images, movies, and supported result tables.
- Builder drafts and undo history are in memory; there is no project autosave/recovery format.
- Loaded-document lists, comparison mappings, and session annotation state are not a saved project/workspace.
- Export MOL to preserve an edited molecule's connectivity and Studio bond annotations.
- XYZ preserves atom order/coordinates, but not bond orders. No complete ASE restart file is generated by the existing selected-geometry XYZ export.
- Local MLIP has a versioned model cache, environment registry and persistent SQLite job database, with immutable inputs, full frames, provenance and MD checkpoints. This does not autosave unrelated builder drafts or the complete desktop workspace.

### Separate browser editor

The repository also contains a standalone browser viewer/editor and a portable HTML packaging path. It has SMILES/structure import, molecular editing, styles, measurements, PNG scale choices, XYZ/MOL/PDB exports, and compressed URL-hash sharing of a molecule and its style.

That is a separate entry point from the Qt desktop. Its share links do not serialize desktop calculation results, cube datasets, comparison sessions, or undo history. It should not be mistaken for the desktop calculation workspace or the native MLIP calculation interface, which belongs to the desktop.

## 12. Packaging, performance boundaries, and verification

### Packaging status

- **Windows:** GUI and MLIP Offline editions, each with an x64 installer and portable ZIP; per-user installation and Start-menu/optional desktop shortcut. Both include the viewer/editor runtime. MLIP Offline also includes CPU calculation environments and five public checkpoints for setup without internet. UMA/MACE-OFF23 weights remain excluded.
- **macOS:** separate Apple Silicon/Intel build workflows and DMG/ZIP packaging. Experimental; physical Mac validation remains pending. Builds are not Apple-notarized.
- **Linux:** source-based execution is available and has been used for desktop checks; there is no equivalent polished Linux installer workflow in this checkout.
- GitHub Actions can build desktop downloads and run checks. Generated installers are Release/artifact files, not source files to commit. The workflows do not automatically publish a GitHub Release.
- Generated renderer/editor assets are committed alongside their sources. Editing JavaScript requires regenerating those assets; using a packaged app does not require Node/npm.

### Existing viewing and export limits

| Limit | Current value or behavior |
| --- | --- |
| General output/trajectory/cube input | 256 MiB per file. |
| Structure import through the desktop loader | 20 MiB for MOL/SDF/PDB. |
| Shared 3D model validation | 10,000 atoms and 40,000 bonds. |
| Saved trajectory import | At most 100,000 frames and 5 million atom positions in total; frames are loaded into memory. |
| Native 2D-to-3D generation | At most 300 heavy atoms; embedding has a time limit. |
| Cube fields | Up to eight loaded cubes; up to 8 million grid samples per file. |
| Studio image rendering | GPU dimension limits and a 24-megapixel internal render limit, including supersampling. |
| Ray tracing | GPU dimension limits, 16-megapixel output limit, and two million triangles per flattened mesh. |
| Video export | At most 10,000 output frames per export. |

These are implementation limits, not a promise that every workload below them is fast on every machine. File loading and native coordinate conversion use background tasks. The separate MLIP queue runs one worker at a time and streams results to SQLite; bounded pages (default 200, maximum 1,000 frames) feed the existing viewer. Optional live previews are limited to once per second.

Existing checks cover parsers, chemistry/editing, fragments, geometry conversion, trajectories, RMSD, input generation, spectra, IRC/scans, shared rendering, fog, annotations, export and measurements. The [MLIP acceptance report](docs/MLIP_ACCEPTANCE.md) records new numerical checks, real public-model jobs, Windows/Linux desktop checks and the Windows review-bundle regression. Successful execution does not establish universal chemistry accuracy or Mac runtime validation.

## 13. Data and source map for MLIP integration

### Calculation data already available

The Python `Calculation` record is the common input to the existing result views:

| Field | Current meaning |
| --- | --- |
| `name` | Display name. |
| `atomnos` | One atomic-number array shared by all frames. |
| `coords` | Cartesian coordinates, shape `[frame, atom, 3]`, in Å. |
| `energies` | Per-frame energy array in Hartree; missing values use NaN. The UI energy label distinguishes saved potential energies from SCF/DFT energies. |
| `metadata`, `summary`, `warnings` | Source metadata, human-readable details, and import limitations. |
| `convergence` | Per-step reported convergence values and targets. |
| `orbitals` | Last reported orbital channels, with energies in eV and HOMO information. |
| `frequencies`, intensities, displacements | Vibrational results and the associated reference geometry. |
| `transitions` | Reported electronic transition data for UV–Vis. |
| `reaction_path` | Path kind, coordinate labels/values, energies, and links into the coordinate trajectory. |

The JavaScript builder/viewer model uses ordered `atoms` with element and x/y/z coordinates, optional per-atom charge/isotope/radical fields, and `bonds` with **zero-based** endpoints, order, and optional dative/TS kind. User-facing atom indices are normally **one-based**. The MLIP runner preserves that correspondence in immutable input snapshots and saved results.

### Persistent simulation data

Local MLIP stores full Cartesian forces, coordinates, masses, charge/spin, constraints, applicable velocities/cell/PBC, explicit settings and model/software provenance. Units are Å, eV, eV/Å, fs and amu; existing `Calculation` energies are converted to Hartree. A bounded adapter supplies existing result views without making the in-memory `Calculation` record the simulation archive.

Imported ASE trajectories additionally retain masses, cell/PBC, charge/spin, velocities and constraint definitions for new input capture. Importing an arbitrary saved trajectory is still not a lossless optimizer/integrator checkpoint round trip. Exact continuation is available only for Studio's own velocity-Verlet/Langevin MD checkpoints with compatible identities/settings/software; other jobs restart from geometry explicitly.

### Source locations

| Concern | Current files |
| --- | --- |
| Desktop orchestration and geometry/result dispatch | [app.py](src/alder/app.py), [ui.py](src/alder/ui.py) |
| Calculation record, Gaussian/ORCA parsing, cube validation | [data.py](src/alder/data.py) |
| Saved ASE/XYZ/geomeTRIC trajectories and unit conversion | [trajectory.py](src/alder/trajectory.py) |
| Gaussian/ORCA setup dialog and text generation | [job_setup.py](src/alder/job_setup.py) |
| Structure comparisons and atom correspondence | [comparison.py](src/alder/comparison.py), [alignment.py](src/alder/alignment.py) |
| Orbitals/vibrations and electronic spectra | [results.py](src/alder/results.py), [spectra.py](src/alder/spectra.py), [uv.py](src/alder/uv.py) |
| IRC/scan records and displays | [paths.py](src/alder/paths.py), [path_view.py](src/alder/path_view.py) |
| Native builder controls and 2D/3D conversion | [builder.py](src/alder/builder.py), [sketch.py](src/alder/sketch.py), [structure.py](src/alder/structure.py) |
| Shared renderer and bridge adapters | [studio-view.js](web/src/studio-view.js), [studio.js](web/src/studio.js), [studio-calculation.js](web/src/studio-calculation.js) |
| Interactive editing, fragments, cleanup | [editor/](web/src/editor/), [build_fragments.py](scripts/build_fragments.py) |
| Measurement math | [measure.js](web/src/measure.js) |
| Images, ray tracing, and movies | [render_export.py](src/alder/render_export.py), [render-export.js](web/src/render-export.js), [raytrace.js](web/src/raytrace.js) |
| Generated offline frontend assets | [assets/](src/alder/assets/), [package-studio.mjs](web/scripts/package-studio.mjs) |
| Packaging and test fixtures | [packaging/](packaging/), [.github/workflows/](.github/workflows/), [tests/data/README.md](tests/data/README.md) |

Relevant existing dependencies include ASE, NumPy, native RDKit, cclib, PySide6/Qt WebEngine, Matplotlib, and Pillow. The frontend uses Three.js, Ketcher, RDKit JS/WASM, a GPU path tracer, and Mediabunny. The bundled 3Dmol asset is used for cube parsing/surface generation; the shared molecular renderer itself is Three.js. MLIP inference dependencies run in separate environments outside the GUI process. The Windows MLIP Offline edition carries the runtime, locked local packages and public weights needed to create those environments offline; the GUI edition downloads them on demand. The explicit model catalogue and weight manager are in `mlip/registry.py` and `mlip/environment.py`. Shared algorithms are in `mlip/engine.py`, execution in `mlip/worker.py`, persistence in `mlip/store.py`, desktop setup in `mlip_ui.py`, and bounded results in `mlip_results.py`.

### Signed dihedrals

The former sign mismatch is resolved. Viewer measurements, input setup, path helpers, constraints and MLIP scans use ASE's signed torsion convention wrapped to **[-180°, 180°)**. The ordered coordinates `(-2,0,0), (0,0,0), (0,2,0), (0,2,2)` give **+90°**. UI indices are one-based; stored atom indices and viewer messages are zero-based. Wrap-boundary tests cover residuals and constrained geometry.

## 14. Local MLIP workflows

The desktop includes separate UMA/FAIR-Chem, MACE and AIMNet2 adapters with explicit checkpoints, local-file manifests, charge/spin/domain validation, device/precision readiness checks and recorded correction settings. **Guided setup** shares installation logic with `alder-setup`: select multiple checkpoints, detect the destination computer's CPU/NVIDIA hardware, check Hugging Face access, install CPU or driver-selected CUDA packages, and verify real energy/forces. Safe repair keeps the registered environment until its replacement passes a real model check. The offline edition uses bundled environments and public weights when CPU is selected; CUDA setup needs online packages. Valid caches are reused, stopping/retrying is supported, and advanced controls can connect an existing environment. Downloads are explicit and checksummed. Hugging Face uses the official credential cache, not calculation records.

Implemented job types are single point with full forces; ASE BFGS/L-BFGS/FIRE optimization; frozen/bond/angle/dihedral constrained optimization; analytical/autodifferentiated or finite-difference frequencies; optimization followed by frequencies; relaxed 1D/2D scans; Sella TS refinement and frequency verification; Sella IRC with optional endpoint optimization; NEB/CI-NEB with linear/IDPP initialization; velocity-Verlet NVE and Langevin NVT; and RDKit conformer sampling followed by MLIP optimization, clustering and ranking.

Linked workflows retain parent job and selected frame. Starting structures come from Build, imports, selected Calculation frames and Compare references. Viewer atom picking supplies constraints/scan indices. Jobs retain progress, elapsed time, logs, convergence/termination, failures and useful partial results. Normal modes, trajectories, energy/path profiles, comparison and figure exports reuse existing views.

See [MLIP.md](docs/MLIP.md) for exact algorithms, settings, traversal, units, data persistence, setup and continuation rules.

## 15. Verified behavior and boundaries

- Public MACE-ANI-CC and AIMNet2-wB97M-D3 member 0 completed every required workflow on Linux aarch64 and Windows x64 CPU. Reaction-path integration checks do not establish a checkpoint's scientific accuracy outside its training domain.
- UMA adapter and FAIR-Chem environment interfaces are implemented and import-checked; real weights/jobs remain pending gated access. MACE-OFF23 weight tests remain pending licence authorization. These are not counted as passed.
- Periodic workflows, constrained TS/IRC/NEB, electronic excited-state prediction, external dispersion stacking and UMA isolated-atom references are not supported. Missing orbitals, densities, IR/Raman intensities and electronic spectra are never synthesized.
- Fresh CPU/CUDA installs and real public-model checks passed on Windows with an RTX 5070. AIMNet2 completed the CUDA workflow matrix; MACE completed all cases except an unconverged reverse IRC. Other GPUs, macOS MLIP runtime and live Hugging Face account authentication remain unverified. See the acceptance record for exact scope.
- Conformer sampling is not a global-minimum guarantee. Deduplication retains atom mapping without symmetry permutations.
- MD output is streamed and paged. Existing movie export operates on the loaded page/band; unbounded full-MD movie assembly is not automatic.
- Windows builds produce GUI and MLIP Offline editions. Generated bundles are excluded from source control and are not included in a source clone. The recorded 22 September 2026 validation did not replace the installed application or publish a release.

The [acceptance matrix](docs/MLIP_ACCEPTANCE.md) distinguishes implemented algorithms, independent numerical tests, real-model checks and unavailable infrastructure.
