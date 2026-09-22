# Local MLIP calculations

Molecule Studio runs molecular calculations in separate Python processes. The desktop viewer/editor remains usable while a job runs. The GUI edition downloads calculation environments on request. The Windows MLIP Offline edition includes CPU environments and public models. Ordinary calculations do not require a terminal; prepared models run offline.

## First use

1. Open **Local MLIP**. On **Calculation**, select MACE, AIMNet2, or UMA and an explicit checkpoint.
2. Click **Set up selected model** (also available on **Environment / models**). The app prepares its own Python, installs the selected backend and calculation tools, detects working devices, prepares the exact checkpoint, and performs a real energy/force readiness calculation. No terminal, system Python or manually entered paths are needed. Allow several GB of disk space per calculator. The GUI edition needs internet for first setup; the MLIP Offline edition uses bundled files for public models.
3. Follow any access/licence prompts. Public MACE-ANI-CC and AIMNet2 checkpoints do not require an account. For UMA, setup reuses an existing Hugging Face login or prompts for a read token with links to the account/token and model-access pages. Restricted checkpoints are downloaded only after acknowledgement. Wait for **ready** before queueing. The readiness calculation uses the captured structure (water if none is captured), device and precision; installing a package alone does not mark a model ready.
4. Capture a 3D structure from Build, an imported structure, a selected calculation frame, or the Compare reference. Confirm **charge and multiplicity**. Select the job, edit its settings, and queue it.
5. On **Jobs / results**, select a job and open a saved page, inspect its forces, or open its final points/band. Results use the existing molecular, energy, vibration, path, comparison, and figure/video export views.

The default public MACE checkpoint is **MACE-ANI-CC**. MACE-OFF23 requires academic/noncommercial licence acknowledgement. UMA requires access to the gated `facebook/UMA` repository. **Connect Hugging Face** sends a read token through the worker's standard input to the official Hugging Face client; it is stored in that client's local credential cache, never in job input, command-line arguments, or job logs. Existing Hugging Face login credentials also work. The access-page button opens the model's access request page. Authentication does not grant model access automatically.

**Set up selected model** runs these steps for the selected backend only; repeat it for any other backend/checkpoint you need. **Queue local calculation** automatically rechecks the selected model when readiness has not been verified in this session (for example, after reopening the app or changing checkpoint/device/precision). It queues the captured input only after a successful check; failure or cancellation queues nothing. This recheck uses existing weights and the registered environment, without downloading or reinstalling anything. For first-time setup or missing weights, use **Set up selected model**; valid environments and cached weights are reused. A missing managed environment is created automatically, and an incompatible managed environment gets one repair attempt. An existing custom environment is probed without modifying its packages. **Advanced setup** retains manual environment connection and individual install/download/check controls.

Setup pauses new queue starts, prevents changing model settings mid-operation, and provides a live log and **Stop setup**. Package installation stops after the current installer operation; downloads/checks can stop immediately. Completed steps remain available on retry. Gated-access denial, invalid login, failed installation, missing dependencies and failed model checks remain explicit errors. Sella failure leaves TS/IRC unavailable, even if other jobs pass readiness.

Downloading or checking a model is explicit through setup. Running a calculation never switches models or downloads missing weights. A checksum mismatch is an error. Model setup and inference messages redact tokens and signed URL queries.

## Windows offline edition

The larger **MLIP Offline** installer/portable ZIP includes:

- Standalone Python 3.12.14, uv, and hashed Windows x64 CPU wheels for three separate environments, including ASE, RDKit and Sella.
- **MACE-ANI-CC** and **AIMNet2-wB97M-D3**, **B97-3c-2025**, **NSE**, and **rxn**, each pinned to ensemble member `_0` and the registry SHA-256.
- Exact dependency locks, checkpoint identities and third-party notices in `mlip-offline` beside the executable.

Choose **Set up selected model** once for each needed calculator. Setup creates a fresh environment at its final local path from the included Python and wheels, then copies and verifies the selected public weights. A terminal, preinstalled Python, Hugging Face account and internet connection are unnecessary for these public checkpoints. Keep the entire portable folder, including `mlip-offline` and `_internal`. Environments are installed under Studio's normal calculation data folder, so moving the portable application does not invalidate an installed calculator. Use **Open setup folder** to find that folder.

UMA's software environment is included; its gated weights are not. MACE-OFF23 weights are also excluded. Those choices still require access/licence acknowledgement and an online download. No login credentials are shipped. CUDA packages are not included; advanced users may connect a compatible CUDA environment and pass the device/model checks. macOS/Linux offline installers are not provided by this build.

Setup verifies the runtime/installer/lock hashes and installs wheels with `--offline --no-index --no-build --require-hashes`; missing or corrupt included files cause an error, never an automatic online fallback. Stop/retry retains completed installation steps. Existing custom environments remain supported. Switching between the GUI and offline editions preserves jobs, cached models and registered environments; uninstalling the app does not delete that separate data.

Maintainer preparation and validation commands are in [Windows packaging](../packaging/WINDOWS.md). The standard [Python venv documentation](https://docs.python.org/3/library/venv.html) explains why environments are recreated at their destination; [uv's offline package options](https://docs.astral.sh/uv/reference/cli/) enforce local installation.

## Workflows and controls

| Job | Execution and saved result |
| --- | --- |
| Single point | Potential energy, every atom's Cartesian force, maximum force, and additional properties actually supplied by the calculator. |
| Optimization | ASE BFGS, L-BFGS, or FIRE; force threshold, step limit, maximum displacement, and FIRE time-step control. Reaching a limit is **unconverged**, not completed convergence. |
| Constrained optimization | Frozen atoms and fixed distances, angles, and signed torsions. Position projection uses ASE internal coordinates; force/momentum projection handles rank deficiency and linear molecules. Every saved step includes target/achieved residuals. |
| Frequencies | Available analytical/autodifferentiated Cartesian Hessian or explicit two-/four-point central differences of forces. Mass weighting, molecular rigid-mode projection, signed imaginary frequencies, vectors and animation. |
| Optimization → frequencies | Separate related optimization and frequency jobs. The parent stays **waiting** until the frequency child finishes. A failed/unconverged optimization does not start a frequency calculation. |
| Relaxed scans | One or two bond/angle/torsion axes, explicit endpoints and point counts, and optimization of all remaining allowed degrees of freedom. Row-major traversal, last axis fastest. Each point starts from the last converged geometry; an unsuccessful point does not become the next starting guess. Failed points and any saved partial geometry remain explicit. No interpolation fills gaps. |
| Transition state | Sella order-one refinement, internal/Cartesian coordinates, search step, derivative step and convergence controls. Optional frequency verification. A converged optimizer is labelled a **verified first-order saddle** only if the full projected analysis contains exactly one significant imaginary mode. |
| IRC | Sella's mass-weighted constrained reaction-path algorithm, forward/reverse/both. Records signed cumulative mass-weighted path length, energies, geometries, settings and each branch's termination. Molecular endpoint verification projects rigid modes to avoid interpreting numerical rotational/translational eigenvalues as negative curvature. Optional endpoint optimization creates child jobs. |
| NEB / CI-NEB | Explicit reactant/product atom correspondence, total image count including endpoints, linear/IDPP initialization, spring and optimizer controls. Every iteration's images are saved with their image and band-iteration identity. The final band and its energy profile are available directly. Its highest image is never automatically called a verified TS. |
| Molecular dynamics | ASE velocity Verlet NVE or Langevin NVT; fs timestep, steps, temperature, seed, saving interval, and friction in fs⁻¹. Saves velocities, potential/kinetic/total energies and temperature. Configurable force/temperature guards stop numerical failure and retain earlier frames/checkpoints. |
| Conformer sampling | RDKit ETKDGv3 candidates with explicit hydrogens and the supplied atom-mapped molecular graph, then MLIP optimization. Connectivity/stereochemistry changes and candidate failures are recorded. Converged unchanged candidates are energy-sorted, filtered by an eV window, and greedily clustered by mapped heavy-atom proper-rotation RMSD. This samples conformers; it does not guarantee the global minimum. |

For **scan/NEB → TS → frequencies → IRC**, open the desired saved point/image, select the next job type, and use **Use selected viewer frame as child input**. The parent job and exact saved-frame index are retained. TS frequency verification can run inside the TS job. Separate frequency children and independent IRC jobs can also be created. **Compare retained conformers / IRC endpoints** adds their structures to Compare for alignment/RMSD; endpoint optimizations are used when saved results exist.

A conformer input must have explicit hydrogens and ordinary bond orders. Recognized isotope masses retain isotope-dependent stereochemistry; arbitrary effective masses are rejected for conformer sampling. XYZ does not supply that graph: prepare it in Build first. Clustering intentionally preserves atom mapping and does not permute symmetry-equivalent atoms; this can retain extra equivalent conformers. Discarded/unconverged candidates remain inspectable.

### Selecting constraints and scan atoms

Use **Pick in viewer**, click atoms in the requested order, return to the setup window, and select **Use picked atoms**. When starting from Compare, picking switches to its reference structure so atoms from separate overlays cannot be mixed. Picks must match the captured input geometry.

Numerical entries use **one-based** atom numbers:

```text
freeze 1 2 3
bond 1 4 1.50
angle 1 4 5 109.5
dihedral 1 4 5 6 -60
```

Scan entries append `start stop points` instead of a single target:

```text
bond 1 4 1.2 2.2 11
dihedral 1 4 5 6 -180 180 25
```

Duplicate/redundant constraints, coincident atoms, collinear torsions, linear constrained angles, invalid atom numbers and invalid targets are rejected. A failed position projection remains an explicit failure. At most 10,000 grid points are allowed per scan. TS, IRC, NEB and conformer sampling currently require unconstrained molecular inputs; constrained optimization, scans, MD and constrained frequency analysis are separate supported workflows.

### Frequencies and scientific interpretation

The unconstrained molecular Hessian is transformed with the supplied masses and projected against the independent translations/rotations (three for an atom, five for a linear molecule, six for a nonlinear molecule). Constrained calculations use the constraint tangent space and Lagrangian curvature, removing only rigid motions allowed by the constraints; they are explicitly marked **partial/constrained**, and cannot verify an unconstrained saddle.

MD temperatures follow ASE’s kinetic-temperature convention (3N degrees of freedom minus explicit constraints). Initial velocities use a seeded Maxwell–Boltzmann draw; unconstrained molecules have initial center-of-mass motion and rotation removed without rescaling. The first saved temperature can therefore differ from the requested initialization temperature. Langevin thermostats act on the retained molecular Cartesian degrees of freedom; monitor equilibration explicitly.

The default significant-imaginary threshold is 20 cm⁻¹, editable in advanced settings. This excludes small numerical rigid/soft-mode noise from the saddle count; it is not evidence that every soft mode is harmless. Inspect modes and repeat with tighter forces/displacements/precision as appropriate. Finite-difference displacement defaults to 0.01 Å. No IR intensities, Raman activities, orbitals, densities, spectra or electronic excited states are manufactured from an energy/force model. The existing vibration panel displays unavailable intensities as blank and uses labelled mode markers.

All torsions now use ASE's signed convention, wrapped to **[-180°, 180°)**. For `(-2,0,0), (0,0,0), (0,2,0), (0,2,2)`, the displayed torsion is **+90°**. Measurements, constraints, Gaussian/ORCA scan setup, MLIP scan residuals and path matching use that convention. Scan ranges may cross a wrap boundary; targets retain the entered traversal and residuals use the shortest angular difference.

## Storage, units and recovery

The application-data `calculations-v1` directory contains `jobs.sqlite`, `models/`, `environments.json`, `env-v1-<backend>/`, and managed `python/`, `tools/` and `package-cache/` directories. Qt selects the current user’s application-data location on Windows, macOS and Linux; nothing needs to be placed beside the executable or edited by hand. **Open setup folder** or **Open job folder** opens it. Hugging Face credentials use the official client’s automatically selected credential location; model files are cached under the app’s `models/` directory. `MOLECULE_STUDIO_MLIP_HOME` can select an alternative root for testing or managed deployments.

The SQLite database stores hashed immutable input snapshots, parent/frame relationships, status/logs, provenance, compressed full frames and associated checkpoints. Each frame/checkpoint pair is committed atomically. One job runs at a time by default. A queue lock prevents two desktop windows from scheduling simultaneously. Workers detect a lost parent; startup distinguishes an active worker from interrupted history.

| Quantity | Canonical stored unit |
| --- | --- |
| Coordinates / cell | Å |
| Potential, kinetic, total energy | eV |
| Forces | eV/Å |
| Hessian | eV/Å² |
| Masses | amu |
| Time / velocities | fs / Å fs⁻¹ |
| Temperature | K |
| Stress, if genuinely returned | eV/Å³ |
| Normal-mode frequencies | cm⁻¹ |
| IRC coordinate | √amu Å |

The existing `Calculation` view receives energy divided by ASE's Hartree-in-eV conversion; raw eV values remain in the database. Atom identity, order, charge/spin, masses, settings, constraints, coordinates, full forces and applicable velocities/cell/PBC are retained. Molecular jobs reject periodic inputs; they do not discard PBC to make an unsupported job run. Imported ASE trajectories now retain masses, cell/PBC, charge/spin, velocities and constraint definitions for input capture. Unsupported imported constraint types require explicit preparation.

Saved pages contain at most 1,000 frames (default 200); live preview, if enabled, refreshes at most once per second. Full MD output is streamed to SQLite, never passed wholesale into the existing in-memory trajectory importer. **Export trajectory** streams all saved frames to extended XYZ plus a provenance JSON sidecar. Normal image/video export operates on the page currently loaded in the viewer; open the needed page/band explicitly. Long full-trajectory movie assembly across multiple pages is not automatic.

**Exact continuation** is supported for NVE velocity Verlet and Langevin NVT checkpoints: positions, velocities, timestep, thermostat settings, step/time and NumPy generator state are restored, with identical model/constraint/settings requirements. It adds another configured segment. Reproducibility also requires the same software/device and deterministic backend execution; a change of GPU/library may change floating-point results. **Restart from last saved geometry** is always a new calculation and does not restore optimizer, NEB, Sella or IRC history. No exact continuation is claimed for those algorithms.

Cancellation is cooperative at each evaluation, with a five-second fallback kill for a hung owned process. Failed/cancelled/interrupted jobs retain previously committed frames. A calculation that reaches its iteration limit is distinguishable from a converged calculation. Model changes, absent files and changed checksums are errors rather than fallback choices.

## Environments and platform status

Managed environments use Python 3.12.14, ASE 3.29.0, NumPy 2.4.3, SciPy 1.17.1, RDKit 2026.3.6, Sella 2.6.0, PyTorch 2.13.0, and separate calculator packages: `mace-torch==0.3.16`, `aimnet[ase]==0.2.0`, or `fairchem-core==2.22.0`. The bootstrap pins uv 0.12.17 and checks its PyPI wheel digest. Each successful setup saves `installed-lock.txt`; jobs record inference and algorithm library versions.

Windows x64 managed CPU environments for MACE and AIMNet2 have been exercised, including Sella installation without a separate compiler. Current managed Windows PyPI PyTorch wheels provide CPU execution. A compatible CUDA environment can be connected; CUDA is offered only if its runtime allocation probe succeeds and the selected model passes a real device check. This development machine has no working CUDA device. Linux aarch64 CPU was also tested. macOS, other Linux architectures, CUDA inference and Hugging Face authentication with a real account remain unverified here. The packaged GUI and worker runtimes are isolated so bundled GUI DLLs do not override calculator libraries.

UMA environment imports were verified without gated weights. Actual UMA energies, forces and every job type remain **unverified pending model access**, as requested. MACE-OFF23 downloads/tests remain pending licence approval. This is recorded in the [acceptance matrix](MLIP_ACCEPTANCE.md), separately from implemented algorithms.

## Compatible local model files

Select a compatible checkpoint file and provide a JSON capability manifest. Supply an independently known SHA-256; do not use a manifest to claim unsupported chemistry. Required fields:

```json
{
  "name": "My compatible MACE checkpoint",
  "backend": "mace",
  "sha256": "REPLACE_WITH_THE_64_CHARACTER_CHECKPOINT_SHA256",
  "elements": [1, 6, 7, 8],
  "domain": "Describe the actual training/validation domain",
  "charge": "neutral",
  "spin": "singlet",
  "periodic": false,
  "properties": ["energy", "forces"],
  "precision": ["float32", "float64"],
  "task": null,
  "head": "Default",
  "correction": "State corrections already included by this checkpoint"
}
```

Local files must implement the selected official calculator interface. Ordinary MACE models in this adapter do not accept charge/spin conditioning; charge-conditioned custom architectures cannot be enabled merely by changing the manifest. UMA uses the `omol` task and requires at least two atoms; isolated-atom reference tables are not loaded by this molecular adapter. AIMNet2 uses checkpoint-owned long-range/Coulomb/D3 metadata, and nonsinglets require an NSE checkpoint. Additional correction stacking is disabled to prevent double counting.

## Sources

Interfaces and package requirements were checked against [FAIR-Chem installation](https://fair-chem.github.io/install/), [UMA tasks](https://fair-chem.github.io/uma/), [MACE foundation-model interfaces](https://mace-docs.readthedocs.io/en/latest/guide/foundation_models.html), [AIMNetCentral](https://github.com/isayevlab/aimnetcentral), [ASE](https://docs.ase-lib.org/), and [Sella's maintained source](https://github.com/zadorlab/sella). Automatic Python/cache paths follow [uv’s documented environment settings](https://docs.astral.sh/uv/reference/environment/); login uses the [official Hugging Face client](https://huggingface.co/docs/huggingface_hub/en/package_reference/authentication). Frozen-process isolation follows [PyInstaller's external-process guidance](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application).
