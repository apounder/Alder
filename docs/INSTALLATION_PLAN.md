# Guided installation and model setup plan

Status: core workflow implemented on 22 September 2026. `install.py`,
`environment.yml`, `molecule-studio-setup`, the shared setup engine, and the native
wizard now exist. Follow the [README](../README.md#installation) for current commands.

Implemented: per-machine CPU/NVIDIA detection, explicit CPU versus driver-selected
CUDA packages, multi-checkpoint selection, early Hugging Face access checks,
licence consent, cache reuse, resumable setup, safe replacement/repair, first-launch
setup, and an interactive Windows installer hook. Fresh Windows CPU/CUDA installs
passed real public-model calculations; see [acceptance](MLIP_ACCEPTANCE.md).

The detailed sections below preserve the target design, not a claim that every
item has shipped. Remaining items include per-model storage estimates and disk
preflight, an explicit multi-GPU selector, dedicated diagnostics export, wider
hardware/platform validation, and rebuilding/testing/publishing desktop releases.
Live account authentication and gated/restricted weights still need authorized
acceptance tests. Package selection currently uses uv's driver-aware PyTorch
selection with pinned Torch, rather than a separately maintained CUDA recipe table.

## Outcome

A person following the GitHub README can install the desktop application, choose
MLIP models, supply any required account access, and complete a real calculation
check through one guided setup. Git/source and Conda installations are primary
entry points. The desktop installer uses the same setup logic.

The walkthrough handles dependency versions, environment paths, checkpoint
downloads, and CPU/GPU configuration. The user chooses models and whether to use
their processor or a compatible NVIDIA graphics card. All selected models must
pass their checks before setup reports full success.

Support initially covers the existing AIMNet2, MACE, and UMA catalogue. Additional
MLIP families require an adapter and tested installation recipe before appearing
as supported choices. Hardware and model compatibility must be explicit: CUDA
support applies to compatible NVIDIA GPUs, not every graphics card.

## Findings before this implementation

- `pyproject.toml` installs the desktop dependencies and a Windows GUI entry
  point. It has no terminal setup command or Conda environment specification.
- `mlip_ui.py` owns the setup sequence inside a Qt dialog. It installs one backend,
  then asks about access, downloads one checkpoint, and runs a readiness check.
- `mlip/environment.py` installs a fixed Torch requirement without selecting a
  CPU/CUDA package source. Its device probe runs inside that environment and does
  not independently identify host hardware or explain why CUDA is absent.
- During the 22 September 2026 setup review, the local AIMNet2 and UMA
  installations contained Torch `2.13.0+cpu` with `torch.version.cuda = None`.
  Their saved device probes listed only CPU. This explains their inability to use
  CUDA; the inspection did not establish driver or hardware health.
- `packaging/windows.iss` installs application files and optionally launches the
  app. It does not run model setup as part of installation.
- Useful foundations already exist: separate backend environments, cached weights,
  hash checks, external workers, setup locking, persistent configuration, token
  redaction, and actual energy/force checks. Preserve and reuse them.

## Entry points

### Git/source checkout

Proposed user commands, with Git and a supported Python already available:

```text
git clone https://github.com/apounder/molecule-studio.git
cd molecule-studio
python install.py
```

`install.py` is a small bootstrap: check prerequisites, create or reuse the local
app environment, install the app, and invoke the terminal walkthrough using the
correct interpreter. It must work without activating the environment. A repeat
run detects existing setup and offers to resume, add models, or repair it.
Print the exact launch command and offer to open the GUI when finished.
Use an existing supported interpreter or the existing verified uv bootstrap
approach where appropriate; report missing prerequisites with one concrete fix.

### Conda

Proposed commands from the downloaded or cloned repository:

```text
conda env create -f environment.yml
conda activate molecule-studio
molecule-studio-setup
```

The environment file installs a tested Python version, pip, and the desktop
package. It also includes Git because the pinned cclib dependency requires it.
Calculator environments remain managed separately so model dependency conflicts
do not affect Conda's base
environment or the GUI. The final command runs the same walkthrough as Git setup.

This is installation using a repository environment file. A literal
`conda install molecule-studio` additionally needs a published Conda package and
channel; do not document that command until the distribution exists.

### Existing pip installations and desktop downloads

Add `molecule-studio-setup` as a console entry point while retaining
`molecule-studio` as the GUI entry point. Include a module invocation fallback for
PATH problems. Windows GUI executables cannot be relied on to provide stdin for
terminal questions.

A first GUI launch with incomplete setup offers the equivalent guided setup.
The Windows installer invokes that wizard after copying application files and
before its interactive completion step. Silent installs use explicit options or
defer model configuration; they must never wait invisibly for input.

Git clone and ordinary pip/Conda dependency transactions do not perform interactive
authentication. The explicit setup command owns questions, progress, and retries.

## Walkthrough

1. **Check this computer.** Identify OS, architecture, installed model environments,
   CPU, NVIDIA hardware, driver, available GPU memory, internet access, and free
   disk space. Show a short readable result. A failed GPU query is distinguishable
   from no GPU. Check the native host used by the app; a WSL result is not proof of
   native Windows readiness.
2. **Choose models.** Offer a small recommended public selection, a custom selection,
   all catalogue models, or viewer only. Present readable names, supported chemistry,
   access requirements, and estimated download/storage size. Expand model families
   into explicit checkpoint choices, including the existing AIMNet2 variants,
   MACE-ANI-CC/MACE-OFF23 sizes, and UMA. Do not choose chemical suitability solely
   from the user's hardware.
3. **Choose calculation hardware.** Default to automatic selection: prefer a tested
   compatible GPU, otherwise explain the CPU choice. Always offer explicit CPU.
   If hardware detection fails, report it and offer Recheck or an explicit CPU
   choice. Explain unavailable GPU support with the reason and a remedy. Select
   the actual GPU on computers with multiple devices; save its identity with the
   preference.
4. **Connect accounts and review licences.** Reuse existing Hugging Face access or
   request a read token with hidden terminal input. Provide links to token creation
   and required model-access pages. Check identity and access to each selected
   restricted repository before downloading uncached weights or their backend
   dependencies. Skip online access checks for verified, cached weights.
   Distinguish an invalid token, insufficient permissions, denied or pending
   access, and network failure.
   Report pending approval only when the service provides that status. Show
   model-specific terms and require acknowledgement where needed. Public models
   do not need an account. Allow pending models to be deferred while others finish.
5. **Confirm and install.** Show models, selected device, location, required space,
   and downloads. Install each backend recipe once, then its selected checkpoints.
   Show stage and real progress information, keeping detailed logs available.
   Ctrl+C or Cancel retains completed work and leaves a resumable setup record.
   Explain when a package operation must finish before cancellation takes effect.
6. **Verify and finish.** Run each selected checkpoint's real energy/force check on
   its selected device. Verify job capabilities separately where necessary, such
   as Sella/TS/IRC and Hessian support. Finish with a per-model result: ready on GPU,
   ready on CPU, awaiting access, or failed with a concrete next action. Offer to
   launch the GUI and run a bundled example. Full success requires every selected
   model to be ready. Partial completion or explicitly deferring a selected model
   must be labelled clearly.

Hugging Face access checks must be available in the setup application before any
calculator environment exists. Bundle the official lightweight client there and
reuse it across both interfaces. Keep credentials in its existing user credential
cache, never in setup plans, arguments, job records, or logs. Support the official
token environment variable for automation without printing or persisting it in
installation reports. Cached models must remain usable offline.

## CPU and CUDA installation

Maintain a small tested recipe table keyed by OS, architecture, backend, and
execution runtime. Each recipe pins Python, Torch build/source, backend packages,
required native wheels, and supported GPU architectures/driver constraints. Choose
from tested recipes; do not synthesize an arbitrary combination from the latest
available packages or the system CUDA toolkit version.

Probe NVIDIA hardware/driver independently of Torch. Then explicitly install the
approved CPU or CUDA Torch build and its compatible dependencies. Pin the runtime
through subsequent dependency resolution so another package cannot silently
replace it with a CPU build. Version validation must recognize approved CUDA build
identities, including local version suffixes where present.

Verify the installed build, GPU access, a synchronized GPU operation, and the actual
selected model on that device. Record GPU identity, driver/runtime versions, recipe
identity, checkpoint hash, precision, and checks. A successful import or
`torch.cuda.is_available()` alone is insufficient. Scope readiness to each
checkpoint/device/precision/runtime combination and invalidate it when those change.
Persist the selected GPU identity and pass it through job configuration and worker
launch. If that GPU becomes unavailable, request a new choice instead of silently
switching to another GPU. A small readiness calculation does not guarantee that
larger jobs fit in GPU memory; report memory failures with practical next steps.

Explain driver updates with an official link and a Recheck action. Do not require
users to choose CUDA toolkit versions or compile dependencies. Driver installation
and any required restart remain explicit OS operations. If no tested GPU recipe
fits, offer CPU and clearly explain the limitation; never report GPU success or
silently change an explicitly requested GPU job to CPU.

The existing offline CPU bundle remains usable offline. Enabling GPU from that
edition is an explicit online operation unless a matching tested GPU bundle is
provided. Do not claim offline GPU support from CPU wheels.

## Repair, persistence, and automation

The same setup command must offer Add models, Check installation, Repair, and
Enable/change GPU. Mirror these actions in a visible **Models and hardware** page
in the app. Show detected GPU hardware separately from whether an installed model
can use it, so CPU packages cannot make a GPU disappear from the interface.

Repair uses cached weights and downloads only missing or changed dependencies.
Build replacement environments at their final, unique paths and switch the active
registration only after verification. Do not relocate virtual environments. Keep
the previous working environment available for rollback. Respect the existing
setup/queue lock and wait for active calculations before switching environments.
Preserve jobs and installed models across app updates and interrupted setup.

Store selected checkpoints, device preference, completed stages, and readiness per
model. Reopening after interruption offers Continue setup. Avoid reasking resolved
choices, repeatedly downloading weights, or announcing success based only on
package installation. Retain completed stages even if one model fails.

Proposed command examples after installation:

```text
molecule-studio-setup
molecule-studio-setup --models all --device auto
molecule-studio-setup --repair --device cuda
molecule-studio-setup --check
```

`--models all` selects all catalogue entries but does not waive access requirements
or accept licences. Add a noninteractive mode with explicit model/device options,
existing credentials, and recorded or explicit model-specific licence acceptance.
It never prompts. Missing requirements produce a clear per-model report and a
nonzero status. Use documented exit statuses for full success, incomplete setup,
failure, and cancellation; already working selections remain usable.

## Implementation sequence

1. **Shared setup logic and runtime selection.** Extract the operation sequence
   from `mlip_ui.py` into a small `mlip/setup.py` module independent of Qt widgets
   and dialogs. The terminal path must run without a graphical session. Extend
   `mlip/environment.py` with hardware diagnostics and explicit runtime recipes.
   Reuse workers, registry, hashes, caches, locks, and persistence. Add the minimum
   persisted setup state required for multiple models and resuming. Use the same
   cross-process lock for CLI and GUI operations, and extend configuration and
   worker handling to preserve the selected GPU.
2. **Terminal path.** Add a stdlib argparse/getpass console interface, console
   entry point, source bootstrap, and `environment.yml`. Implement early account
   checks, multi-model choices, all-model selection, progress, cancellation,
   repair, and noninteractive operation. Test both Git and Conda entry paths.
3. **GUI parity and existing installations.** Connect the existing Qt controls and
   a guided first-use flow to that same setup module. Add the visible hardware and
   repair page. Import existing environments and offer CPU-to-GPU conversion while
   retaining model caches. Make CLI and GUI resolve exactly the same data location.
4. **Installer and GitHub delivery.** Invoke guided setup from the Windows
   installer. Put Git/Conda setup instructions and downloadable releases prominently
   in the README. Keep maintainer build steps elsewhere. Publish tested release
   artifacts through a separate release workflow; ordinary setup never depends on
   users finding expiring Actions artifacts.
5. **Release verification.** Verify the entry paths and supported model/device
   combinations on real target systems. Record results and advertise only those
   combinations that have passed. Windows x64 is the first acceptance target given
   the reported problem; use the same architecture for Linux CPU/CUDA and macOS
   CPU, with separate platform checks before claiming support.

Keep one setup implementation with terminal and Qt interfaces. Reuse the existing
package manager and model workers; no separate service, plugin framework, or new
workflow framework is needed for these requirements.

## Acceptance criteria

- A fresh Windows user with Git/Python or Conda follows the documented commands
  and completes setup without editing paths, JSON, or environment variables.
- A fresh standalone install works without system Python, Git, Conda, or Node.
- Public AIMNet2 and MACE-ANI-CC installation succeeds without a Hugging Face account;
  real permitted UMA access and licence-gated model branches are exercised.
- A compatible NVIDIA machine with existing CPU-only model packages can select
  Enable GPU, complete a real GPU calculation, and keep its existing weights/jobs.
- Every advertised backend/device combination passes real model checks and
  representative jobs, including derivative-dependent jobs where advertised.
  CPU results and GPU results agree within defined model/precision tolerances.
- Test absent GPUs, failed hardware probes, old drivers, unsupported GPU
  architectures, insufficient GPU memory, and incorrect installed Torch builds.
  Each case has a clear remedy and a usable CPU choice where supported.
- Test all-model installation, one failed model among successes, denied/pending
  access, unavailable internet, insufficient storage, cancellation, restart,
  rollback, and cached repeat setup. Interrupted work resumes without losing
  successful installations or redownloading verified checkpoints.
- CLI and GUI show identical installed models and device readiness. Neither
  exposes credentials in logs/reports nor silently changes requested devices.
- The CLI works without a display, missing stdin never leaves it waiting for input,
  and simultaneous CLI/GUI setup cannot modify the same environment. Existing
  environments and verified cached weights can be checked offline without
  prompting for credentials or contacting Hugging Face.
- Existing calculator installations and jobs survive the migration. Setup does
  not repeat every app launch; model checks reuse existing environments/weights.
- Mock tests cover failure branches; actual NVIDIA hardware and real authorized
  gated-model access are release gates for the corresponding support claims.

## External references

- The [PyTorch installation guide](https://pytorch.org/get-started/locally/)
  describes selecting the compute runtime and verifying GPU availability.
- [NVIDIA CUDA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)
  defines driver/runtime compatibility constraints; use these with tested recipes.
- [Hugging Face gated models](https://huggingface.co/docs/hub/models-gated)
  explains that account authentication and approval to download a model are distinct.
- [Conda environment management](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html)
  documents repository environment files and installing pip requirements inside
  isolated Conda environments.
