# Alder

![Alder logo and reaction profile](docs/assets/alder-header.png)

An offline desktop application for viewing computational chemistry results,
building molecules, running local MLIP calculations, and exporting figures. Calculation files and structures
are processed locally.

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
  [setup guide](docs/MLIP.md) and [tested compatibility](docs/MLIP_ACCEPTANCE.md).
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

Choose one route below. Each installs the desktop app and provides a walkthrough
for model selection, CPU/GPU setup, and any required Hugging Face access.
Calculation environments and downloaded models are saved for future launches.

| How you want to install | Start here | What you need first |
| --- | --- | --- |
| Download a desktop app | [Windows installer or portable download](#1-desktop-download) | A matching release, when available |
| You already use Anaconda or Miniforge | [Conda](#2-conda) | Conda and an extracted or cloned copy of this repository |
| Download GitHub's source ZIP | [Source ZIP](#3-source-zip) | Python 3.11 or newer and Git (for a dependency) |
| Clone with Git | [Git](#4-git-clone) | Git and Python 3.11 or newer |

For first-time model setup, use an internet connection and allow several GB of
free disk space per calculator. CUDA packages need additional space. Public
AIMNet2 and MACE-ANI-CC models need no account. UMA requires Hugging Face access;
MACE-OFF23 requires licence acknowledgement.

“All models” means the supported catalogue: four AIMNet2 checkpoints, MACE-ANI-CC,
three MACE-OFF23 sizes, and UMA-s-1p2. Other MLIP families need an integration;
arbitrary Hugging Face models are not automatically compatible.

### 1. Desktop download

Open [GitHub Releases](https://github.com/apounder/alder/releases) and
choose the download for your computer. **If no matching release is available,
use the Conda or source instructions below.** A source ZIP is not a desktop installer.

On Windows 10 (1809+) or Windows 11, download the x64 **Setup.exe**, open it,
and follow the installation and model setup windows. Then open **Alder**
from the Start menu. Python, Conda, Git, and Node.js are not required.

Alternatively, download a **Portable.zip**, right-click it, choose **Extract All**,
and open `Alder.exe` inside the extracted folder. Keep `_internal` beside
the executable and, if included, the complete `mlip-offline` folder. Do not run
the executable from inside the ZIP.

| Windows edition | What is included |
| --- | --- |
| **GUI** | Viewer, editors, and exports. The walkthrough downloads your selected calculation environments and weights. |
| **MLIP Offline** | The same app, plus CPU environments and five public checkpoints. These can be set up without internet. GPU setup needs an online CUDA download; UMA and MACE-OFF23 weights are not included. |

The guided installer described here requires a release built from this version
of the source. Older downloads may only have the earlier **Set up selected model**
screen. A fresh portable launch also offers the walkthrough. Existing users can
open **Local MLIP → Environment / models → Guided setup** at any time.

macOS downloads are experimental: choose the matching Apple Silicon or Intel DMG,
drag **Alder** into **Applications**, and open it. Use CPU for calculations;
CUDA requires NVIDIA hardware on Windows or Linux. See the
[macOS guide](packaging/MACOS.md) for current validation and first-launch details.
Linux users should use Conda or source installation and have a graphical session
with the system libraries required by Qt WebEngine.

Windows builds are unsigned; macOS builds are not Apple-notarized.

### 2. Conda

Download this repository using **Code → Download ZIP** and extract it, or clone it
with Git. Open Anaconda Prompt or a terminal where `conda` works, then change to
the extracted `alder` or `alder-main` folder.

Run these commands one at a time; continue after each succeeds:

```sh
conda env create -f environment.yml
conda activate alder
alder-setup
```

The first command installs Python, Git, and the desktop dependencies in their own
environment. The last command walks through all selected model installations.
There is no need to find model Python paths or install PyTorch yourself.

For later launches:

```sh
conda activate alder
alder
```

If you already created this Conda environment using the previous instructions,
update the app from the repository folder and start the new walkthrough:

```sh
conda activate alder
python -m pip install --upgrade .
alder-setup
```

This route uses the repository's `environment.yml`. A published
`conda install alder` package is not currently provided.

### 3. Source ZIP

1. Install [Python](https://www.python.org/downloads/) 3.11 or newer if needed.
   On Windows, enable **Add Python to PATH**, then reopen your terminal.
2. Install [Git](https://git-scm.com/downloads) and reopen your terminal. The pinned
   cclib parser needs Git even when Studio itself comes from a ZIP. If you prefer
   not to install these prerequisites separately, use the Conda route above.
3. On the GitHub repository page, choose **Code → Download ZIP**, then extract it.
4. Open a terminal in the extracted folder containing `install.py` and run:

```powershell
python install.py
```

On macOS or Linux, use `python3 install.py` if your Python command is `python3`.
Setup creates a local `.venv`, downloads a suitable app Python when needed,
installs the desktop dependencies, and starts the model walkthrough. You do not
need to activate `.venv`. The pinned cclib source is downloaded automatically
using Git. Node.js and npm are not needed for this route.

Launch later from that folder on Windows:

```powershell
.\.venv\Scripts\python.exe -m alder
```

Or on macOS/Linux:

```sh
./.venv/bin/python -m alder
```

### 4. Git clone

Run these commands in PowerShell, Anaconda Prompt, or your terminal:

```sh
git clone https://github.com/apounder/alder.git
cd alder
python install.py
```

On macOS/Linux, use `python3 install.py` if needed. Cloning downloads the source;
`install.py` installs the app and starts the walkthrough. Later launch commands
are the same as for the source ZIP above.

## The setup walkthrough

The terminal and desktop walkthroughs use the same setup code and model cache.

1. **Choose models.** Select individual checkpoints, the recommended public models,
   or all supported models. The terminal also accepts backend names such as
   `aimnet2`. Choose `none`, or uncheck all models in the GUI, for the viewer only.
2. **Choose hardware.** Automatic mode checks the current computer for an NVIDIA
   GPU and driver. You can explicitly choose CPU or CUDA. A failed hardware scan
   gives an error and a recheck/CPU choice.
3. **Connect Hugging Face when required.** Setup explains which selected models
   need an account and checks access before downloading their calculation packages.
4. **Install and verify.** Setup installs the selected dependencies, downloads
   weights, and runs a real energy/force calculation on the selected device.
   A model is marked ready only after that check passes.

For UMA, open the [model access page](https://huggingface.co/facebook/UMA), sign in,
and request/accept the required access. Create a
[read token](https://huggingface.co/settings/tokens) permitted to read the model,
then paste it into setup's hidden token field. Existing Hugging Face logins are
reused. A valid token does not itself grant gated-model approval. Setup reports
access problems and retains successfully installed models so you can retry later.

Tokens are handled by the official Hugging Face client and are not saved in job
records or setup reports. Public models and verified cached weights do not require
a new login. You are asked to acknowledge restricted checkpoint licences before
downloading them; choosing “all” does not bypass those requirements.

## CPU and NVIDIA GPU support

Hardware detection runs on **each computer during setup**, independently of any
existing model environment. CPU setup explicitly requests CPU PyTorch packages.
CUDA setup asks the package manager to select the official CUDA build for that
computer's driver, then verifies GPU allocation and the actual model calculation.
See [uv's PyTorch integration](https://docs.astral.sh/uv/guides/integration/pytorch/)
for the underlying package selection mechanism.

| Your hardware | Calculation choice |
| --- | --- |
| Windows/Linux with a supported NVIDIA GPU and driver | Automatic or CUDA; CPU remains available |
| Windows/Linux without a working NVIDIA GPU | CPU |
| macOS, or AMD/Intel graphics without NVIDIA CUDA | CPU; Apple GPU/ROCm acceleration is not implemented |

A compatible NVIDIA driver is required. Setup handles the application packages;
if the driver is missing or outdated, use the
[official NVIDIA driver download](https://www.nvidia.com/Download/index.aspx),
restart if requested, and recheck. Installing a separate CUDA Toolkit is not part
of the normal setup. Older GPUs, incompatible drivers, or unavailable package
builds may require CPU. GPU memory also limits molecule size. Real hardware test
results and remaining limits are listed in [MLIP acceptance](docs/MLIP_ACCEPTANCE.md).

**If you previously installed CPU-only packages:** open **Local MLIP → Environment /
models → Guided setup**, choose **NVIDIA graphics card (CUDA)**, and continue.
Or, in your activated Conda/app environment, run:

```sh
alder-setup --device cuda
```

The walkthrough creates a replacement when needed, reuses cached model weights,
and registers the replacement only after a successful calculation. Existing jobs
and the previous environment are retained. Close the GUI before running terminal
setup, or use Guided setup inside the GUI.

## Add models, repair, or resume later

In an activated app environment:

```sh
alder-setup
alder-setup --models all --device auto
alder-setup --repair --device cuda
alder-setup --check
```

For the source installer on Windows, use
`.\.venv\Scripts\python.exe -m alder setup` with the same options;
on macOS/Linux, use `./.venv/bin/python -m alder setup`.
If a command is not on PATH, `python -m alder setup` also works inside
the activated app environment.

Repeat setup after an interruption. Completed environments and verified weights
are reused; failed models remain clearly identified. Cancel may wait for the
current package installation to finish. Use **Repair** for a broken environment.
Use **Check** to verify existing packages and weights without downloading them.
Reopening the app does not reinstall models.

For unattended public-model setup, explicitly provide the choices:

```sh
alder-setup --models recommended --device cpu --non-interactive
```

Restricted-model automation can use an existing Hugging Face login or `HF_TOKEN`,
and `--accept-license CHECKPOINT` for each licence you have reviewed and accepted.
Never put a token in a command argument. Incomplete setup returns a nonzero exit
status; it does not report failed or inaccessible models as ready.

### Common setup problems

| What you see | What to do |
| --- | --- |
| `py` is not recognized | Use `python install.py`; these instructions do not require the Windows `py` launcher. |
| `python` or `git` is not recognized | Install the prerequisite, reopen your terminal, and retry, or use the Conda route. |
| `.venv\Scripts\python.exe` does not exist | The app installation did not finish. Rerun `python install.py` and resolve its first error. |
| GPU detected but CUDA check fails | Update the NVIDIA driver, reopen Guided setup and choose CUDA/Repair; CPU is also available. |
| Hugging Face returns access denied | Check model approval and token permissions; a valid token alone is not approval. Other public models do not need it. |
| An interrupted or failed model installation | Rerun setup; use Repair for a damaged environment or checksum failure. Keep the cached models and job folder. |

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
access/licence approval. Follow the [MLIP guide](docs/MLIP.md) for job settings,
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

## Development

Requires Python 3.11+, Git, and working OpenGL/WebGL graphics. Linux also needs
the system libraries required by Qt WebEngine. From the repository root,
create and activate a virtual environment, then run:

```sh
python -m pip install ".[dev]"
alder
```

Run the Python tests with `python -m pytest -q`. Run
`python -m pytest tests/test_mlip_engine.py -q` in a compatible calculation
environment for the additional Sella checks. Real-checkpoint and packaged-app
commands are in the [acceptance guide](docs/MLIP_ACCEPTANCE.md). Desktop integration tests in
`tests/*_smoke.py` require a graphical session.

Bundled renderer and editor assets are included in the repository. Editing
them requires Node.js; see [web development instructions](web/README.md).
Use the platform guides above to build standalone releases. Test-data
provenance and licenses are documented in [tests/data](tests/data/README.md).
