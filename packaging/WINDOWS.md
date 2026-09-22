# Windows releases

Windows releases include an x64 installer and a portable ZIP. The build
workflow checks the application, installation, and uninstall behavior before
uploading the downloads.

Local downloads are in `dist/release`. To publish the already-built files,
attach the installer, ZIP, and checksums to a GitHub Release after publishing
the source repository. You do not have to rebuild just to try this local app.

## Build with GitHub's website — no local command line

1. Put the contents of **molecule-studio** at the root of a GitHub repository.
   Include `.github/workflows/windows.yml`, `packaging`, `scripts`, `src`, `web`,
   `tests`, `pyproject.toml`, and `run_studio.py`. Exclude `.venv`, `.runtime`,
   `.build-tools`, `node_modules`, `build`, and `dist`. The checked-in editor HTML and JS already contain their
   dependencies; this workflow does not run npm. The editable renderer and
   builder sources are included in `web` for development.
   If using GitHub's browser uploader, `sketch.html` is about 30 MB and exceeds
   its 25 MB per-file limit. GitHub Desktop can commit and push the source
   folder without a terminal. Keep `.github` included even if your file manager
   normally hides folders beginning with a dot.
2. In the repository, open **Actions → Windows download → Run workflow**.
   The workflow must be on the default branch for this button to appear.
3. Wait for a green build. It checks the parsers, builds the app, runs the actual
   executable with Python removed from PATH, installs it, checks the installed
   copy, and uninstalls it. Internet requests from its embedded editor are
   blocked during the application check.
4. Open the successful run and download the **MoleculeStudio-Windows-x64**
   artifact. Extract it to obtain the installer, portable ZIP, and SHA-256
   checksums. Actions artifacts require a GitHub login and expire after 30 days.
5. Test the installer on a normal Windows PC. Then open **Releases → Draft a
   new release**, choose/create the tag `v0.3.1`, and attach the installer,
   portable ZIP, and `SHA256SUMS.txt`. Publish when ready. Public release assets
   provide the easy, lasting download for users without a GitHub account.

The workflow also builds version tags and pull requests. It does not publish
releases automatically and does not require repository write permissions.
Increase `project.version` in `pyproject.toml` for the next release.

In GitHub Desktop, open the repository, commit the changes, and choose
**Push origin**. For a new repository, choose **Publish repository** after the
first commit. Attach generated downloads to Releases; build tools and build
output are excluded from source control.

## What the download contains

- A console-free `MoleculeStudio.exe` with its own Python runtime, PySide6/Qt
  WebEngine, native RDKit, calculation parsers, and offline 2D/3D/WASM assets.
- A per-user Inno Setup installer, Start-menu shortcut, optional desktop
  shortcut, and entry in Windows **Settings → Apps → Installed apps**.
- A portable folder in a ZIP. Extract the complete folder before launching it.
- A `START-HERE.txt`, dependency build information, and third-party notices.

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
.venv-build\Scripts\python.exe scripts/build_windows.py
```

Downloads are written into `dist/release`. A compiler installed outside the
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
`%LOCALAPPDATA%\Molecule Studio\studio.log`. Its smoke report lists completed
checks and the first exception. Build success checks the runner, not every
Windows graphics driver: still verify rotation, file drops, vibration playback,
surfaces, and a high-resolution figure on a real PC before publishing.

The application check can also be invoked explicitly from PowerShell:

```powershell
& .\MoleculeStudio.exe --smoke-test "$env:TEMP\studio-check.json" "C:\path\to\molecule-studio\tests\data"
```

References: [PyInstaller's build model](https://pyinstaller.org/en/stable/operating-mode.html),
[Inno Setup per-user installation](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm),
[GitHub artifact downloads](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts).
