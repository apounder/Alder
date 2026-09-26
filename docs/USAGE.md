# Using Alder

[Back to the quick start](../README.md#installation) · [Screenshot tour](../README.md#interface-and-results)

## Features

- Gaussian and ORCA results: optimization trajectories, energies, orbital
  levels, animated vibrations, and UV–Vis spectra from reported excited states.
- IRC profiles and 1D/2D scan maps with linked geometries and path playback;
  unrestricted, CPCM/SMD solvent, and MP2 jobs.
- Multiple loaded calculations, structure overlays, rigid alignment, RMSD,
  explicit atom correspondence, individual structure colors, and adjustable playback speed.
- Gaussian/ORCA input setup with live preview and local input-file export.
- Local UMA, MACE and AIMNet2 calculations: energies/forces, optimization and
  constraints, frequencies, scans, TS/IRC, NEB, MD and conformer sampling, with
  managed environments, a persistent queue and saved partial results. See the
  [setup guide](MLIP.md) and [tested compatibility](MLIP_ACCEPTANCE.md).
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

Click **Measure** above the canvas and choose **Bond length**, **Angle**, or
**Dihedral**, then pick 2, 3, or 4 atoms in order. For an angle, pick its vertex
second; for a dihedral, pick along the four-atom torsion. The readout shows atom
indices and Å or degrees, with a dashed guide on the structure. Distances can
also be measured between unbonded atoms. **Clear** or Escape resets the picks;
click Measure again to close the tool. The same tool works in Calculation,
Compare, Figure, and 3D Build. Values update during trajectory/vibration playback
and builder drags; new calculations clear the picks.

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

**Local MLIP** runs calculations in separate, reusable environments. Use **Guided
setup** to select models, configure CPU/CUDA, and supply required access. Then
capture a structure and queue a job. Cached models work offline. Existing Python
environments and compatible local checkpoints remain available under **Advanced
setup**. Public MACE-ANI-CC and AIMNet2 have real Windows CPU/CUDA checks and
historical Linux CPU checks. UMA and MACE-OFF23 weight validation remain pending
access/licence approval. Follow the [MLIP guide](MLIP.md) for job settings,
constraints, continuation and platform limits.

Saved ASE/Sella trajectories and geomeTRIC optimization XYZ can also be opened
without running a model. Energies are converted to Hartree for the existing
views; plain XYZ requires an explicit energy unit. Atom identities/order must
match across frames. Periodic files display stored Cartesian coordinates; local
MLIP workflows reject periodic inputs. Missing orbitals, electronic spectra,
IR intensities and Raman activities remain unavailable.

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

**View → Shared 3D appearance** includes five xyzrender-inspired presets: Flat,
Tube, Ball and tube, Wire, and vdW. These adapt the
[xyzrender styles](https://xyzrender.readthedocs.io/en/latest/configuration.html)
to Alder's interactive 3D renderer. You can still adjust the representation,
outlines, projection, and atom size after selecting a preset.

Under **Figure → Figure add-ons**, enable **Automatic NCI contact lines** or
**Translucent van der Waals spheres** (5–60% opacity). Both are included in
Studio and ray-traced images and update with trajectory/movie frames. Add-ons
do not change bonds, exported molecular structures, or calculation coordinates.
Use **Fit** after enabling spheres if they extend beyond the current framing.

Contact lines are geometry-based suggestions: teal for explicit hydrogen bonds
(N/O/S–H···N/O/S/F, angle at least 120°, H···acceptor ≤2.7 Å and donor···acceptor
≤3.6 Å), purple for Cl/Br/I halogen contacts (angle at least 150°), and gray for
other short heavy-atom contacts within 95% of the sum of vdW radii. All pairs
must be between 55% and 100% of that radius sum; directly bonded, 1–3, and 1–4
neighbors are excluded. Enable hydrogens to display H-bond lines. Supported
radii are H, C, N, O, F, P, S, Cl, Br, and I; other elements are skipped by these
add-ons. This is a distance/angle heuristic, not a full interaction assignment:
it does not perceive aromatic centroids, classify π-stacking, or calculate
interaction energies. For density-based NCI surfaces, continue using the cube
field controls.

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

