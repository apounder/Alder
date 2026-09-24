# MLIP compatibility and acceptance

Validated on 2026-09-22. “Implemented” and “tested with real weights” are separate claims. Model correctness outside the reported training domain is not established by successful execution.

## Guided installation: fresh CPU and CUDA checks

The new shared source/terminal/desktop setup was tested on native Windows 11 x64,
with a 20-thread Intel CPU and NVIDIA RTX 5070 (12 GB, driver 610.74). Tests used
separate, initially empty calculation folders, not the user's working environments.

| Check | Result |
| --- | --- |
| Source bootstrap into a new app environment | Passed: managed Python 3.14.7, desktop dependencies and terminal setup |
| Conda environment file and installed setup command | Passed: new Conda environment, automatic NVIDIA detection and real cached CUDA checks for both public backends |
| Freshly installed desktop smoke checks | 16 passed, including Qt WebEngine, Gaussian/ORCA import, 2D/3D editing and figure/video exports |
| New AIMNet2 and MACE CPU environments | Passed: PyTorch 2.13.0+cpu, Sella imports, real water energy/forces |
| New AIMNet2 and MACE CUDA environments | Passed: driver-selected PyTorch 2.13.0+cu132, GPU allocation, Sella imports, real water energy/forces |
| AIMNet2-wB97M-D3 CUDA workflow matrix | All 14 required workflow cases completed, including TS/IRC, NEB, MD and conformers |
| MACE-ANI-CC CUDA workflow matrix | 13 of 14 completed; reverse IRC reported `IRCInnerLoopConvergenceFailure`, retained partial results and was correctly marked unconverged |
| Windows Python suite | 115 passed, 1 skipped (Sella absent in the desktop test interpreter); includes four isolated native walkthrough scenarios |
| Linux setup logic tests | 16 passed, 1 skipped (Qt unavailable in that test interpreter); this is not Linux CUDA validation |

CUDA numerical checks also passed: maximum water force/energy-derivative errors
were `8.27×10⁻⁴ eV/Å` for AIMNet2 and `6.63×10⁻⁵ eV/Å` for MACE (limit `0.002`).
Analytical/finite-difference frequency differences were `1.81 cm⁻¹` and
`1.29 cm⁻¹`, respectively (limit `5`). The MACE IRC convergence failure is not
counted as a full-matrix pass; readiness verifies execution, not convergence for
every scientific calculation. See [guided setup evidence](validation/mlip-guided-setup.json).

Missing-driver/no-GPU hosts, failed queries, cached access, gated denial,
secret redaction, cancellation, CPU-to-CUDA replacement, preservation after a
failed GPU check, and check-only behavior have automated simulated coverage.
The real CPU tests explicitly selected CPU on the NVIDIA-equipped host.
Real Hugging Face login/UMA weights, MACE-OFF23 weights, other GPU families,
macOS runtime, and the rebuilt desktop installer remain unverified. None is
included in the new pass claims. Existing downloadable executables must be
rebuilt and tested before distributing this walkthrough.

## Job matrix

The shared engine uses the selected ASE calculator without model-specific optimizer/path/dynamics implementations.

| Required workflow | MACE-ANI-CC CPU | AIMNet2-wB97M-D3 member 0 CPU | UMA-s-1p2 / omol |
| --- | --- | --- | --- |
| Single point, full forces | Real Linux + Windows pass | Real Linux + Windows pass | Implemented; gated weights pending |
| BFGS / L-BFGS / FIRE optimization | All three real Linux + Windows pass | All three real Linux + Windows pass | Same algorithms; real validation pending |
| Constrained optimization | Real Linux + Windows pass | Real Linux + Windows pass | Same algorithm; real validation pending |
| Frequencies / optimization → frequencies | Real analytical Hessian + linked workflow pass | Real autodifferentiated Hessian + linked workflow pass | Finite-difference fallback implemented; real validation pending |
| Relaxed 1D scan | Real Linux + Windows pass | Real Linux + Windows pass | Real validation pending |
| Relaxed 2D scan | Real Linux + Windows pass | Real Linux + Windows pass | Real validation pending |
| Sella TS + frequency verification | Ammonia inversion, one imaginary mode | Ammonia inversion, one imaginary mode | Real validation pending |
| Both-direction IRC | Ammonia paths to molecular minima | Ammonia paths to molecular minima | Real validation pending |
| NEB / climbing-image NEB | Real IDPP CI-NEB pass; independent linear-band test | Real IDPP CI-NEB pass | Real validation pending |
| NVE / NVT MD | Both real Linux + Windows pass | Both real Linux + Windows pass | Real validation pending |
| RDKit → optimization → conformer clustering | Explicit-H ethane, real Linux + Windows pass | Explicit-H ethane, real Linux + Windows pass | Real validation pending |

MACE-ANI-CC's ammonia reaction path is a **technical integration test**, not validation of its reaction chemistry. Its training domain is neutral organic conformations. An applicable reactive checkpoint/reference calculation is needed for scientific conclusions.

## Checkpoint compatibility

| Checkpoint | Elements | Charge / spin | Domain and corrections | Precision |
| --- | --- | --- | --- | --- |
| MACE-ANI-CC | H C N O | Neutral, singlet only; no charge/spin conditioning | ANI-1ccx small organic molecular domain; learned coupled-cluster reference, no additional D3 | float32 / float64 |
| MACE-OFF23 small / medium / large | H C N O F P S Cl Br I | Neutral, singlet only | Organic molecules/molecular phases; reference includes dispersion; additional D3 disabled. Academic/noncommercial licence | float32 / float64 |
| AIMNet2-wB97M-D3 `_0` | H B C N O F Si P S Cl As Se Br I | Explicit net charge; singlet only | Isolated organic/main-group molecules/clusters. Checkpoint's Coulomb and D3 parameters used | float32 |
| AIMNet2-B97-3c-2025 `_0` | Same 14 elements | Explicit net charge; singlet only | B97-3c molecular/intermolecular domain. Checkpoint-owned corrections | float32 |
| AIMNet2-NSE `_0` | Same 14 elements | Explicit net charge and multiplicity | Open-shell molecular chemistry; not strongly multireference systems. Checkpoint-owned corrections | float32 |
| AIMNet2-rxn `_0` | H C N O | Neutral, singlet in this adapter | Reactive molecular HCNO paths; checkpoint-owned Coulomb/D3. Its energy reference differs from other families | float32 |
| UMA-s-1p2, `omol` | Atomic numbers 1–83 exposed by this molecular adapter | Explicit charge and multiplicity; documented API bounds checked | OMol25 molecular domain; broad element coverage is not proof for arbitrary oxidation/spin states. No added dispersion | float32 |

All exposed workflows are **nonperiodic**. Some underlying calculators/checkpoints have periodic interfaces; this does not provide a complete or validated periodic Studio workflow. Cell/PBC are preserved, and periodic jobs are rejected. No orbital, density, electronic-spectrum, IR or Raman prediction is claimed. AIMNet2 supplies model atomic charges; NSE can additionally supply spin charges. Runtime properties remain absent when a calculator does not return them.

Named model identities are explicit files/members, SHA-256 digests and immutable source revisions in `mlip/checkpoints.json` / `mlip/registry.py`. UMA points to Hugging Face revision `f611b917d9c68566bbbeccbb0aa0f7cad1696cb2`. MACE-ANI-CC SHA-256 is `7ad311c590b7df90a1d4aa34d997a8c419fdb7ae777296350869614e9e07b69d`. AIMNet2-wB97M-D3 `_0` SHA-256 is `f0f7c054539ad3261bd36f9b11c56d12f87cb723e25bea7521755bbd3ec24e28`. Package defaults and short moving aliases are not used.

Additional public AIMNet2 B97-3c-2025, NSE (OH doublet), and rxn checkpoints passed real Linux CPU energy/force checks; their complete job matrix has **not** been repeated. MACE-OFF23 was not downloaded, per the requested licence policy. UMA's separate FAIR-Chem 2.22.0 environment and exact inference-setting constructor were imported successfully, but **no UMA calculation is reported as passed**.

## Numerical checks and tolerances

- All Cartesian water force components were compared with central energy derivatives at ±0.001 Å. Maximum errors: MACE `6.62×10⁻⁵ eV/Å`; AIMNet2 `7.13×10⁻⁴ eV/Å`. Acceptance tolerance: `2×10⁻³ eV/Å`, allowing float32 energy differencing and central-difference truncation without accepting a units/sign error.
- Analytical/autodifferentiated vs central-force-difference water frequencies at 0.01 Å: maximum differences `1.29 cm⁻¹` (MACE) and `1.81 cm⁻¹` (AIMNet2). Check threshold `5 cm⁻¹` for this test, not a claim of physical model accuracy.
- Bond constraints: `10⁻⁵ Å`; angular constraints: `10⁻³°`. Independent tests include frozen/duplicate/singular inputs and a torsion crossing the −180/180 boundary.
- Harmonic diatomic isotope frequencies follow the inverse-square-root mass relation to `10⁻⁷` relative tolerance. Rigid-mode rank and constrained/frozen-atom mode counts are tested.
- TS verification requires optimizer convergence and exactly one frequency below the editable significant-imaginary threshold (default −20 cm⁻¹). Ammonia tests met it for both public backends. IRC branches have opposite signed coordinates and distinct endpoints; a failed inner loop is retained with its actual termination, never called a valid completed IRC.
- Independent NEB tests preserve each image's band iteration/frame association and explicitly leave `verified_ts=false`.
- Harmonic NVE short-run energy change is below `10⁻⁵ eV/atom`. A split Langevin run with checkpoint continuation matches an uninterrupted run to `10⁻¹²` in positions and velocities on the same test platform. Real-model MD checks establish short-run execution/stability, not long-time equilibration or thermodynamic accuracy.
- Clustering uses proper rotations (no reflections), heavy atoms and fixed atom mapping. A chiral reflection is not accepted as a zero-RMSD match. RDKit sampling enforces initial 3D stereochemistry, including recognized isotope masses; changed connectivity/stereochemistry and optimization failures are retained and excluded from ranking.
- Input hashing, atom order, periodic rejection, charge/spin policies, missing weights, unsupported elements, unsupported devices/precision, extra-correction rejection, one-active-job claims, cancellation, simulated memory failure, and interrupted partial results are covered independently.

Tests are `tests/test_mlip_engine.py`, `tests/test_mlip_results.py`, `tests/test_mlip_setup.py`, `tests/mlip_setup_smoke.py`, `tests/mlip_real_models.py`, and `tests/mlip_smoke.py`. After automatic setup was added, **95 Python tests passed, one skipped, on both Windows and Linux** in the GUI-only environments; the suite also runs five isolated Qt setup scenarios; **31 shared algorithm tests passed on both Linux and Windows** in calculation environments, including the Sella check skipped by the GUI environment; **20 JavaScript core tests passed**. Existing parser/editor/renderer checks remain separate regressions.

## Desktop and packaging

The real Qt desktop queue, model readiness, optimization → frequency relationship, vibration viewing, cancellation, exact MD checkpoint persistence, bounded pages, and job-history recovery have been exercised on Linux aarch64 and Windows x64. The 22 September 2026 validation produced Windows GUI and MLIP Offline bundles under the ignored `dist/Alder` and `dist/Alder-MLIP-Offline` directories, with downloads in `dist/release`. These generated files are not included in a source clone. That validation did not replace the installed application or publish a release.

Packaged checks use `Alder.exe --mlip-smoke-test REPORT PYTHON CACHE` with the external calculation interpreter and public model cache. `--smoke-test REPORT FIXTURES` exercises Gaussian/ORCA viewing, offline editing, comparison/input generation, surfaces and figure/video exports. Both packaged checks passed. The final MLIP check also created a fresh managed AIMNet2 environment through the packaged UI, then exercised real model readiness, optimization → frequencies, mode viewing, cancellation, bounded results and recovery after an actual worker termination. The saved [validation evidence](validation/mlip-acceptance.json) distinguishes these passes from unavailable configurations.

Automatic setup was also verified in the updated Windows standalone executable with a **new managed Python installation and an uncached public AIMNet2 checkpoint**, using only the in-app setup action. Repeating setup reused the environment and weights. The resulting environment passed real readiness, optimization → frequencies, cancellation/checkpoint and restart-recovery checks. Five isolated Qt scenarios cover simulated login/licence branches, cancellation, retry, cache reuse and unavailable devices on both Windows and Linux. See [automatic setup evidence](validation/mlip-auto-setup.json). Real account authentication and restricted weight downloads remain pending.

Those earlier packaged checks used CPU environments and did not validate CUDA. The newer source-install CUDA checks are recorded above. Real account login, UMA/MACE-OFF23 weights and macOS runtime remain pending; none is counted as passed.

The subsequent readiness fix was checked on Windows and Linux with seven focused tests, including eight isolated Qt scenarios. The rebuilt Windows executable was closed and reopened before queueing an AIMNet2 optimization: queueing automatically rechecked cached weights and submitted the captured input. Optimization → frequencies, cancellation and history recovery passed. Failed or cancelled readiness checks queue nothing. See [readiness-after-restart evidence](validation/mlip-readiness-fix.json).

## Windows offline edition validation (0.4.0)

- **98 Python tests passed, one skipped** in both Windows and Linux GUI test environments. The GUI interpreter lacks Sella; each separate calculation environment passed its Sella import check. Native light-control checks passed on Windows and Linux after deliberately starting from a dark palette, covering editable/read-only/disabled fields and checkbox states.
- Fresh Windows x64 Python environments for **AIMNet2, MACE and UMA** were installed exclusively from bundled, hashed wheels. All passed CPU and Sella probes with worker networking denied. All five bundled public checkpoints passed real water energy/force checks: MACE-ANI-CC and AIMNet2 wB97M-D3, B97-3c-2025, NSE and rxn (member 0). Repeated local installation reused the environments. UMA weights and MACE-OFF23 remain excluded, with no real UMA calculation claimed.
- The initial calculation checks all passed; the test harness then encountered Windows MAX_PATH while deleting temporary PyTorch licence files. Extended-path cleanup was verified separately on a path over 350 characters and removed the original environment tree. The checked-in test now uses that cleanup. See [offline environment evidence](validation/mlip-offline-windows.json), including this distinction.
- The actual frozen **MLIP Offline** app completed first-use AIMNet2 setup from its bundle with Python removed from PATH and offline/proxy restrictions enabled. Cache reuse, readiness after restart, optimization → frequencies, mode viewing, cancellation, exact MD checkpoint retention, bounded previews and interrupted-job history passed. The packaged viewer also passed Gaussian/ORCA viewing, comparison, input generation, 2D/3D editing, fog/bonds, transparent/ray-traced figures and a normal-mode WebM. See [packaged desktop evidence](validation/mlip-offline-desktop.json).
- GUI and MLIP Offline installers/portable archives are generated from these verified bundles. Installation/uninstallation checks for each edition are included in the Windows GitHub workflow; that remote workflow has not been run from this working tree. The local installed application has deliberately not been replaced. Offline packaging is Windows x64 only; this local validation used x64 emulation on Windows ARM64. CUDA and macOS/Linux offline packages remain unverified.

## Known boundaries

- Exact continuation covers NVE/Langevin MD only. Optimization, scans, NEB, TS and IRC can restart from saved geometry, with a new job and explicit parent relationship; their internal optimizer state is not advertised as resumed.
- Periodic calculations, constrained reaction-path searches, electronic excited states and model-external dispersion stacking are not exposed. UMA isolated atoms are rejected because its separate atomic-reference tables are not loaded.
- A conformer graph requires explicit H and ordinary bonds. Standard atomic weights and recognized isotope masses are supported; arbitrary effective masses cannot define isotope stereochemistry. Symmetry permutations are not used for deduplication, so equivalent conformers may be retained.
- Long trajectories are paged; existing movie export covers the loaded page/band, not an unbounded automatic full-MD movie.
- Finite differences/Hessians scale poorly with system size. Memory failure is an explicit failed job with partial results, not an automatic switch of model, precision or algorithm.

## Reproducing checks

From the repository root, use a calculator environment with pytest for the independent suite:

```sh
python -m pytest tests/test_mlip_engine.py -q
python tests/mlip_real_models.py --backend mace --cache PATH_TO_MODEL_CACHE --output TEMP_RESULTS_DIRECTORY
python tests/mlip_real_models.py --backend aimnet2 --cache PATH_TO_MODEL_CACHE --output ANOTHER_TEMP_DIRECTORY
```

Add `--numerics-only` for all nine water energy/force derivatives and the analytical/finite-difference frequency comparison. The runner fails if a required job is incomplete or a tolerance is exceeded. It never downloads weights. UMA uses the same runner after access, explicit download and environment setup; do not count missing infrastructure as a pass.

Add `--device cuda` to the real-model runner when using a verified CUDA
environment. To exercise the installer itself with public models, use an app
environment and an explicit disposable destination (this downloads packages):

```sh
python tests/guided_setup_real.py --root .build-tools/check-cpu --models recommended --device cpu
python tests/guided_setup_real.py --root .build-tools/check-cuda --models recommended --device cuda
```

The CUDA command requires compatible NVIDIA hardware and its driver. Each runner
returns a nonzero status on failure. Keep test roots separate from user data.

The normal GUI environment runs `python -m pytest -q` and the existing graphical smoke scripts. `tests/mlip_smoke.py` additionally accepts the `MLIP_TEST_PYTHON` and `MLIP_TEST_CACHE` environment variables for real external-worker checks. For a packaged app, use `--mlip-smoke-test REPORT PYTHON CACHE`; setting `MLIP_SMOKE_SETUP=1` also creates a fresh temporary managed AIMNet2 environment through the in-app setup path. Set `MLIP_SMOKE_AUTO_SETUP=1` instead to exercise **Set up selected model** with a new Python installation, dependencies, an uncached public AIMNet2 checkpoint, and a repeated cached setup. This uses the same smoke-test command signature; its supplied interpreter/cache are not used for the automatic-setup branch. Use a graphical session, and allow setup network access. All test databases/environments remain separate from ordinary user jobs.
