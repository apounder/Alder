# Windows releases

Windows releases provide **GUI** and **MLIP Offline** editions, each as an x64 installer and a portable ZIP. Both editions use the same application. The build
workflow checks the application, installation, and uninstall behavior before
uploading the downloads.

After a successful local build, downloads are in `dist/release`. Generated
installers are not included in a source clone. To publish the built files,
attach the installer, ZIP, and checksums to a GitHub Release. To try an existing
build, download its installer or portable ZIP; rebuilding is unnecessary.

## Build with GitHub's website — no local command line

1. Put the contents of **alder** at the root of a GitHub repository.
   Include `.github/workflows/windows.yml`, `packaging`, `scripts`, `src`, `web`,
   `tests`, `pyproject.toml`, and `run_alder.py`. Exclude `.venv`, `.runtime`,
   `.build-tools`, `node_modules`, `build`, and `dist`. The checked-in editor HTML and JS already contain their
   dependencies; this workflow does not run npm. The editable renderer and
   builder sources are included in `web` for development.
   If using GitHub's browser uploader, `sketch.html` is about 30 MB and exceeds
   its 25 MB per-file limit. GitHub Desktop can commit and push the source
   folder without a terminal. Keep `.github` included even if your file manager
   normally hides folders beginning with a dot.
2. In the repository, open **Actions → Windows download → Run workflow**. Leave **Build the larger offline CPU edition** enabled to generate both downloads.
   The workflow must be on the default branch for this button to appear.
3. Wait for a green build. It checks the parsers, builds the app, runs the actual
   executable with Python removed from PATH, installs it, checks the installed
   copy, and uninstalls it. Internet requests from its embedded editor are
   blocked during the application check.
4. Open the successful run and download **Alder-Windows-x64-GUI**
   or **Alder-Windows-x64-MLIP-Offline**. Extract the chosen artifact to
   obtain its installer, portable ZIP and SHA-256 checksums. Actions artifacts require a GitHub login and expire after 30 days.
5. Test the installer on a normal Windows PC. Then open **Releases → Draft a
   new release**, choose/create the tag `v0.4.0`, and attach the installer,
   portable ZIP, and `SHA256SUMS.txt`. Publish when ready. Public release assets
   provide the easy, lasting download for users without a GitHub account.

Manual and version-tag builds produce both editions by default. Pull requests run the GUI checks without downloading the large calculation kit. It does not publish
releases automatically and does not require repository write permissions.
Increase `project.version` in `pyproject.toml` for the next release.

In GitHub Desktop, open the repository, commit the changes, and choose
**Push origin**. For a new repository, choose **Publish repository** after the
first commit. Attach generated downloads to Releases; build tools and build
output are excluded from source control.

## What the download contains

- A console-free `Alder.exe` with its own Python runtime, PySide6/Qt
  WebEngine, native RDKit, calculation parsers, and offline 2D/3D/WASM assets.
- A per-user Inno Setup installer, Start-menu shortcut, optional desktop
  shortcut, and entry in Windows **Settings → Apps → Installed apps**.
- A portable folder in a ZIP. Extract the complete folder before launching it.
- A `START-HERE.txt`, dependency build information, and third-party notices.
- MLIP Offline additionally contains a standalone Python 3.12 runtime, exact hashed wheel sets for MACE/AIMNet2/UMA CPU environments, and five public checkpoints: MACE-ANI-CC plus AIMNet2 wB97M-D3, B97-3c-2025, NSE and rxn (member 0).

Public-model first setup with **CPU** selected in the offline edition installs only local files. No
system Python or internet is needed. Environments are recreated at their final
paths, avoiding paths from the build computer. UMA/MACE-OFF23 weights are excluded;
access/licence approval and a subsequent online download remain necessary.
The offline kit excludes credentials, user jobs and configuration. CUDA and
macOS/Linux offline kits are not part of this Windows build.

New builds run `Alder.exe --setup` during interactive installation;
silent installs skip prompts. A fresh portable launch also offers the same wizard.
It detects the destination computer, checks account access, and installs selected
models. CUDA uses online driver-selected packages, not the bundled CPU wheels.
Existing release downloads must be rebuilt to include this behavior; the new
installer/wizard combination still needs packaged interactive acceptance testing.

The installer does not claim `.log` or `.out` file associations. Open/drop files
inside Studio. It does not modify or uninstall your calculation files. No
auto-updater or background server is installed. The bundle uses a folder so Qt
WebEngine and the chemistry libraries do not need extracting on every launch.

The application icon and installer use Studio's existing green diamond mark.
These initial builds are unsigned; code signing requires a publisher identity
and credentials that are not part of this checkout.

## Build locally on Windows (maintainers only)

Install Python **3.14 x64**, Git, and **Inno Setup 6.3 or later**. End users do not
need these tools. From the repository in PowerShell:

```powershell
py -3.14 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install -r packaging/windows-requirements.txt ".[dev]"
.venv-build\Scripts\python.exe -m pytest -q
.venv-build\Scripts\python.exe scripts/prepare_mlip_offline.py
.venv-build\Scripts\python.exe tests/mlip_offline_smoke.py --bundle .build-tools/mlip-offline --report build/offline-environments-smoke.json
.venv-build\Scripts\python.exe scripts/build_windows.py --offline-kit .build-tools/mlip-offline
```

Preparation downloads public dependencies/models and requires internet on the
build machine. `--environment-root` may point to existing managed build environments;
all backends must pass CPU and Sella probes. Wheel locks contain exact versions and
SHA-256 hashes; no source compilation occurs on the end user's machine. Notices
are included. The offline smoke check recreates every environment in a fresh path
with network connections denied and runs real public-model energy/force checks.
The packaged app then exercises fresh AIMNet2 setup, optimization/frequencies,
cancellation and history recovery.

Omit `--offline-kit` to build only the GUI edition. Downloads are written into
`dist/release`, with `-GUI-` or `-MLIP-Offline-` in their names. A compiler installed outside the
standard Inno Setup location must have `ISCC.exe` on PATH. The script checks the
portable app; the GitHub workflow additionally checks installation/uninstall.
The actual Windows executable must be built on Windows; PyInstaller does not
cross-compile it on Linux.

## Verification and diagnostics

The bundled smoke check loads real Gaussian and ORCA outputs, checks orbital
and vibrational data, generates ethanol with bundled JavaScript RDKit, opens
the 2D editor, converts back with native RDKit ETKDG/MMFF, and exports MOL plus
a transparent PNG. It exercises paths with spaces and non-ASCII characters.
Software WebGL is enabled only for the CI virtual display; ordinary app users
use their graphics drivers.

If the build fails, download **Windows-build-diagnostics** from the Actions run.
The packaged app writes startup output to
`%LOCALAPPDATA%\Alder\studio.log`. Its smoke report lists completed
checks and the first exception. Build success checks the runner, not every
Windows graphics driver: still verify rotation, file drops, vibration playback,
surfaces, and a high-resolution figure on a real PC before publishing.

The application check can also be invoked explicitly from PowerShell:

```powershell
& .\Alder.exe --smoke-test "$env:TEMP\studio-check.json" "C:\path\to\alder\tests\data"
```

References: [PyInstaller's build model](https://pyinstaller.org/en/stable/operating-mode.html),
[Inno Setup per-user installation](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm),
[GitHub artifact downloads](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts).
