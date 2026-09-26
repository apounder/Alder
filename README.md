# Alder

A desktop app for opening chemistry calculation results, building molecules, and
making figures. Your structures and calculation files stay on your computer.
**The viewer, editors, and figure exports work without installing any ML models.**

[Desktop downloads](#desktop-downloads) · [Install from source](#installation) · [Open your first file](#open-your-first-file) ·
[Get model access](#optional-models-and-hugging-face-access) ·
[See the interface](#interface-and-results) · [Rendering examples](#rendering-styles)

## Desktop downloads

Windows users can install Alder with **Setup.exe**, which includes Python and
the graphical setup wizard. For Mac and Linux, use the [macOS](#macos) or
[Linux](#linux) terminal installation instructions to open the same GUI.

1. Open [GitHub Releases](https://github.com/apounder/alder/releases).
2. Under **Assets**, download `Alder-<version>-Windows-x64-GUI-Setup.exe`.
3. Open the file and follow the installation and model setup windows.
4. Later, open **Alder** from Start or its optional desktop shortcut.

No separate Python, Git, Conda, or terminal is needed for the Windows installer.
The portable ZIP is an alternative: extract the complete folder and open
`Alder.exe`, keeping `_internal` beside it.

If no installer is published yet, use [source installation](#installation).
Maintainers can follow the [Windows release guide](packaging/RELEASING.md) to
build and publish it from GitHub. Mac and Linux builds do not block this release.

**First launch:** the **Set up Alder** window lets you choose optional MLIP models
and CPU/NVIDIA hardware. Uncheck every model for the viewer only, or select models
and follow **Next** through access checks and installation. Model downloads need
internet and disk space. For UMA, follow [Hugging Face access](#get-access-to-uma-step-by-step).

**Later launches:** open the same app icon. Installed models are reused. To add,
repair, or change models, use **Local MLIP → Environment / models → Guided setup**.

Windows builds are unsigned.

## Installation

Use the terminal instructions below to install from this repository. You need
internet for the initial download; viewing local files works offline afterward.
Run each command separately and continue only when it succeeds.

| Your computer | Start here |
| --- | --- |
| Windows 10 (1809+) or Windows 11, x64 | [Windows: PowerShell installation](#windows) |
| Windows with Anaconda, Miniconda, or Miniforge | [Windows: Conda installation](#windows-with-conda) |
| Mac, Apple Silicon or Intel | [macOS: Terminal installation](#macos) |
| Linux desktop | [Linux installation](#linux) |
| Already use Anaconda or Miniforge? | [Conda instructions](docs/INSTALLATION.md#2-conda) |

**You do not need a `dist` folder, EXE, or DMG for these instructions.** `dist`
contains local build output and is excluded from GitHub. Desktop installers are
an [alternative only when attached to a release](docs/INSTALLATION.md#1-desktop-download).

### Windows

1. **Install the prerequisites.** Install [Python 3.11 or newer](https://www.python.org/downloads/windows/)
   and [Git for Windows](https://git-scm.com/install/windows). If the Python
   installer offers **Add Python to PATH**, enable it. Then close any existing
   terminal windows and open **PowerShell** from the Start menu.
2. **Check the installation.** Run:

   ```powershell
   python --version
   git --version
   ```

   The first command must report Python **3.11 or newer**; the second must report
   a Git version. If a command is not recognized or Python opens the Microsoft
   Store instead, resolve that before continuing; see [troubleshooting](docs/INSTALLATION.md#common-setup-problems).
3. **Download Alder.** These commands put it in an `alder` folder in your user
   home folder:

   ```powershell
   Set-Location ~
   git clone https://github.com/apounder/alder.git
   Set-Location alder
   ```

4. **Install and start setup.** Run this from the folder containing `install.py`:

   ```powershell
   python install.py --launch
   ```

   Wait for the app dependencies to install, then follow
   [Finish the terminal setup](#finish-the-terminal-setup) below. Enter `none` at
   the model prompt if you only want the viewer. Alder opens after successful setup.
5. **Open Alder again later.** Double-click **Alder Source** on your desktop or
   open it from Start. The terminal fallback is:

   ```powershell
   Set-Location ~/alder
   .\.venv\Scripts\python.exe -m alder
   ```

Setup creates **Alder Source** shortcuts for this Python installation. Keep the
`alder` folder, including its `.venv` subfolder; the shortcuts use that environment. If you cloned
elsewhere, use that location in step 5. You do not need to activate `.venv` or
change PowerShell's execution policy.

### Windows with Conda

This route installs Python, Git, and Alder together in an environment named
`alder`. You can use a source ZIP, so a separate Git installation is not needed.

1. **Open a Conda prompt.** If you already have Anaconda, Miniconda, or Miniforge,
   open **Anaconda Prompt** or **Miniforge Prompt** from the Start menu. Otherwise,
   follow the [official Conda Windows installation guide](https://docs.conda.io/projects/conda/en/stable/user-guide/install/windows.html)
   first. Run `conda --version` and check that it reports a version.
2. **Download the source.** On [Alder's GitHub page](https://github.com/apounder/alder),
   choose **Code → Download ZIP**, then right-click the downloaded ZIP →
   **Extract All**. Open the extracted folder containing `environment.yml`.
   If you already cloned Alder, use that checkout instead.
3. **Enter that folder in the Conda prompt.** Copy its path from File Explorer's
   address bar. Use `cd /d` followed by the path in quotes. For example:

   ```bat
   cd /d "%USERPROFILE%\Downloads\alder-main"
   ```

   Replace the example path with your actual folder. Run `dir environment.yml`
   to confirm you are in the right place.
4. **Install and open setup.** Run one command at a time, waiting for each to succeed:

   ```bat
   conda env create -f environment.yml
   conda activate alder
   alder-setup --launch
   ```

   Follow [Finish the terminal setup](#finish-the-terminal-setup). Enter `none`
   for the viewer only, or select the models you want. Alder opens when setup
   succeeds. This route uses the Conda environment; skip `install.py` and the
   `.venv` commands from the PowerShell route.
5. **Open Alder again later.** Use **Alder Source** on your desktop or in Start.
   To launch from a Conda prompt instead, run:

   ```bat
   conda activate alder
   alder
   ```

The setup command creates **Alder Source** shortcuts pointing to this Conda
environment. Keep the environment installed. These launchers do not create a
redistributable Setup.exe; use the desktop release workflow to build installers.

You can launch from any folder after activating the environment. To add models
later, use **Local MLIP → Environment / models → Guided setup**, or close Alder
and run `alder-setup --launch` in the activated environment. For updates or an
existing `alder` environment, see the [Conda maintenance instructions](docs/INSTALLATION.md#2-conda).

### macOS

The Mac runtime remains experimental and has not been validated on a Mac in this
project's [test record](docs/MLIP_ACCEPTANCE.md). These instructions install from
source; they do not require a DMG. Choose CPU for optional calculations; Apple
GPU acceleration is not implemented.

1. **Install Python.** Download a standard macOS installer for **Python 3.11 or
   newer** from [python.org](https://www.python.org/downloads/macos/) and follow
   its prompts. In Finder, open **Applications → Python 3.x** for the version
   you installed and double-click **Install Certificates.command** to complete
   its HTTPS setup. See the [official Python Mac instructions](https://docs.python.org/3/using/mac.html#installation-steps).
2. **Install Git if needed.** Press **Command+Space**, type **Terminal**, and open
   it. Run `git --version`. If macOS offers to install its Command Line Tools,
   accept and wait for completion. If Git is unavailable and no prompt appears,
   run this, follow the installer, and wait for it to finish:

   ```sh
   xcode-select --install
   ```

   This is the Command Line Tools route in the [official Git Mac instructions](https://git-scm.com/install/mac).
3. **Check the prerequisites.** Close and reopen Terminal, then run:

   ```sh
   python3 --version
   git --version
   ```

   Check that Python is **3.11 or newer** and Git reports a version. The Python
   supplied with Apple's developer tools may be older; use the Python you
   installed in step 1.
4. **Download and install Alder.** Run:

   ```sh
   cd ~
   git clone https://github.com/apounder/alder.git
   cd alder
   python3 install.py --device cpu --launch
   ```

   Wait for app dependencies to install, then follow
   [Finish the terminal setup](#finish-the-terminal-setup). Enter `none` for the
   viewer only. This command already selects CPU, so there is no hardware prompt.
5. **Open Alder again later.** In Finder, open your home folder → **Applications**
   → **Alder Source.app**. You can drag it to the Dock. The terminal fallback is:

   ```sh
   cd ~/alder
   ./.venv/bin/python -m alder
   ```

Keep the `alder` folder and its hidden `.venv` subfolder: **Alder Source.app**
launches this environment. If you cloned elsewhere, use that path in the terminal fallback.
Run Alder's installation and launch commands as your normal user, without `sudo`.

### Linux

Use a normal graphical desktop session. These commands are for **Ubuntu 24.04**;
other distributions need equivalent Python, Git, and Qt runtime packages.

1. Open **Terminal** (Ctrl+Alt+T on Ubuntu). Run these commands one at a time.
   `sudo` may ask for your Linux password; no characters appear while you type it.

   ```sh
   sudo apt update
   sudo apt install python3 git libegl1 libopengl0 libnss3 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0 libxcb-render-util0 libxcb-shape0 libxcb-randr0 libxcb-sync1 libxcb-xfixes0 libxcb-xkb1 libx11-xcb1 libsm6 libice6 libgl1 libxkbcommon-x11-0 libasound2t64
   ```

2. Download Alder into a new folder and enter it:

   ```sh
   git clone https://github.com/apounder/alder.git
   cd alder
   ```

3. Install the app and open it with model downloads skipped:

   ```sh
   python3 install.py --models none --device cpu --non-interactive --launch
   ```

   Wait for installation to finish. The installer creates a `.venv` folder with
   Alder's Python and dependencies. Node.js and PyTorch are not needed for this route.

4. On later visits, open **Alder Source** from the applications menu. The terminal
   fallback, from the same `alder` folder, is:

   ```sh
   ./.venv/bin/python -m alder
   ```

If Qt reports a missing library, consult its [Linux runtime requirements](https://doc.qt.io/qt-6/linux-requirements.html)
and the [troubleshooting guide](docs/INSTALLATION.md#common-setup-problems).

### Finish the terminal setup

`install.py` creates a private `.venv` with Alder's Python and desktop
dependencies, then opens a **text-based walkthrough in the same terminal**.
With Conda, `conda env create` installs the app and `alder-setup --launch` opens
the same walkthrough in the activated `alder` environment. Setup also creates
**Alder Source** launchers, so later launches do not need a terminal. Use
`--no-shortcuts` to skip launcher creation on a server or managed installation.
You do not need to install Node.js or PyTorch yourself. If you used Linux's
`--non-interactive` command above, these prompts are skipped and the viewer opens.

| Prompt | What to enter |
| --- | --- |
| **Models to set up** | Enter `none` for the viewer, builders, and figure exports. Enter `recommended` for the public AIMNet2 and MACE-ANI-CC models, or use the displayed model numbers. Pressing Enter accepts the displayed default, which is normally `recommended` on first setup. |
| **Calculation device: auto, cpu, or cuda** | When shown, enter `cpu` for processor calculations or `auto` to detect a supported NVIDIA GPU on Windows/Linux. Mac instructions already select CPU. Choosing `none` skips this question. |
| **Model access/licence questions** | Only appear for selected restricted models. Read their terms first. UMA also needs [Hugging Face approval and a read token](#get-access-to-uma-step-by-step); pasted tokens stay hidden in the terminal. Public models need no login. |
| **Continue with setup? yes/no** | Enter `yes`. Optional model downloads can require several GB. Wait for installation and verification to finish. |

The `--launch` option opens Alder when setup succeeds. Start with
[Open your first file](#open-your-first-file) below. If setup reports an error,
read the first error and use [troubleshooting](docs/INSTALLATION.md#common-setup-problems)
before repeating the same install command. Completed model installations are
retained. On later visits, use the **Alder Source** app icon or the terminal fallback
instead of running `install.py` again.

**Add models later:** in Alder, open **Local MLIP → Environment / models → Guided
setup**. For the terminal walkthrough, close Alder, return to the same `alder`
folder, and run the command for your system:

Windows:

```powershell
.\.venv\Scripts\python.exe -m alder setup --launch
```

macOS:

```sh
./.venv/bin/python -m alder setup --device cpu --launch
```

For a source ZIP instead of Git, follow the [ZIP instructions](docs/INSTALLATION.md#3-source-zip).
For repairs, checks, or updates, see [ongoing setup](docs/INSTALLATION.md#add-models-repair-or-resume-later).

## Open your first file

1. Open Alder and click **Open files** at the top, or drag a file into the window.
   Use a Gaussian `.log`, ORCA `.out`, or molecular `.xyz` file.
2. Try [gaussian-opt.log](tests/data/gaussian-opt.log) if you do not have a file
   handy. On its GitHub page, click **Download raw file**, save it, and open that
   downloaded file in Alder. Source downloads already include it in `tests/data`.
3. Drag the structure to rotate it and scroll to zoom. Click a point in
   **Energy profile**, move the geometry slider, or press **Play** to inspect the steps.
4. For **Vibrations**, open [gaussian-freq.log](tests/data/gaussian-freq.log);
   for **UV–Vis**, open [gaussian-td.log](tests/data/gaussian-td.log).
5. To save a molecular image, choose a style from **View → Shared 3D appearance**,
   then click **Export figure**. Choose a filename ending in `.png` or `.tif`.

Only results present in the file appear. A plain XYZ contains geometry and will
not produce orbital levels or spectra. These examples come from cclib;
[their sources and licences](tests/data/README.md) are included.

## Optional models and Hugging Face access

MLIP means *machine-learning interatomic potential*: a model that estimates
energies and forces for local calculations. Add these when you want Alder to
run calculations, rather than just view existing output files.

Open **Local MLIP → Environment / models → Guided setup**. Choose your models,
then **Processor (CPU)** or **Automatic — detect this computer**. CUDA needs a
supported NVIDIA GPU and driver. Allow several GB per calculator and more for
GPU packages; setup downloads the packages and checks each selected model.

| Model available in Alder | Account/access needed | What to do |
| --- | --- | --- |
| AIMNet2 checkpoints | No account | Select a checkpoint in Guided setup. |
| MACE-ANI-CC | No account | Select it in Guided setup. |
| UMA (`uma-s-1p2`) | Hugging Face account, model approval, and a read token | Follow the steps below. |
| MACE-OFF23 (small, medium, large) | Separate licence acknowledgement | Read the [model owner's terms](https://github.com/ACEsuit/mace-off), then acknowledge them in setup if they apply to your use. No Hugging Face login is used for this download. |

### Get access to UMA, step by step

1. [Create a Hugging Face account](https://huggingface.co/join), or sign in.
2. Open the [official facebook/UMA model page](https://huggingface.co/facebook/UMA).
   Read the conditions, complete its access form accurately, and submit it.
   Follow the page's approval instructions before attempting the download.
3. Once your account has access, open [Settings → Access Tokens](https://huggingface.co/settings/tokens).
   Create a **read** token, or a **fine-grained** token permitted to read
   `facebook/UMA`. Use the same account that received model access.
4. Return to Alder's **Guided setup**, select **uma-s-1p2**, and proceed to
   **Model access and licences**. Paste your token into the masked **Hugging Face
   read token** field. A token is a password-like credential; keep it private.
5. Acknowledge the terms you have reviewed, then continue. Wait for the download
   and calculation check to succeed before using the model. The official client
   saves the login locally, and downloaded weights are reused on later launches.

A token identifies your account; it does **not** grant model approval. If you see
“access denied,” check both the model page and the token permissions. See
[Hugging Face's gated-model guide](https://huggingface.co/docs/hub/models-gated)
and [token guide](https://huggingface.co/docs/hub/security-tokens).

UMA and MACE-OFF23 end-to-end model validation remains pending access/licence
approval in this project's [test record](docs/MLIP_ACCEPTANCE.md). Alder installs
its supported catalogue, not arbitrary models found on Hugging Face.
For job settings, model domains, repairs, and offline use, read the [MLIP guide](docs/MLIP.md).

<details>
<summary>See the model setup window</summary>

![Alder setup listing optional models and CPU or GPU hardware choices](docs/assets/screenshots/setup.png)

</details>

## Interface and results

The calculation details sit on the left, the structure viewer on the right, and
results tabs below it. Click any image to view it at full size.

![Alder displaying a Gaussian optimization, molecular geometry, and linked energy profile](docs/assets/screenshots/overview.png)

These are captures of the running Windows app using included calculation files.
The plots show reported calculation data. Fonts and window decorations may differ
on other operating systems.

### Energy profile and step data

Click a point or a table row to inspect its geometry. Example:
[gaussian-opt.log](tests/data/gaussian-opt.log).

| Energy profile | Step data |
| --- | --- |
| ![Relative energy across five optimization steps](docs/assets/screenshots/energy-profile.png) | ![Absolute and relative energies for each geometry](docs/assets/screenshots/step-data.png) |

### Orbital levels and vibrations

Select an orbital to highlight its energy, or select a vibration and press
**Play mode**. Example: [gaussian-freq.log](tests/data/gaussian-freq.log).

| Orbital levels | Vibrations |
| --- | --- |
| ![Occupied and virtual orbital energies with the HOMO and LUMO](docs/assets/screenshots/orbital-levels.png) | ![Normal-mode frequencies, IR intensities, spectrum, and animation controls](docs/assets/screenshots/vibrations.png) |

### UV–Vis and IRC / Scans

Adjust spectrum broadening or click a scan-map cell to inspect a calculated
point. Try [gaussian-td.log](tests/data/gaussian-td.log) and
[gaussian-scan2d.log](tests/data/gaussian-scan2d.log), respectively.

| UV–Vis | IRC / Scans |
| --- | --- |
| ![Reported transitions and a broadened calculated absorption spectrum](docs/assets/screenshots/uv-vis.png) | ![Two-dimensional energy scan map with linked geometries](docs/assets/screenshots/scan-map.png) |

<details>
<summary>See the molecule builder</summary>

Use **Build** to draw or edit in 2D/3D, enter SMILES, add fragments, and adjust
hydrogens. Save with **Export MOL** to preserve bond orders; drafts are not saved
automatically when you close the app.

![Alder's 3D molecule builder displaying caffeine and editing tools](docs/assets/screenshots/builder.png)

</details>

## Rendering styles

Choose a preset under **View → Shared 3D appearance**. These are actual **Studio**
exports of the same illustrative caffeine geometry, generated with RDKit. Flat,
Tube, Ball and tube, Wire, and vdW are inspired by
[xyzrender's styles](https://xyzrender.readthedocs.io/en/latest/configuration.html).
The presets also set representation, outlines, and projection defaults.

| Studio | Paton-inspired |
| --- | --- |
| ![Caffeine in the Studio preset](docs/assets/screenshots/style-studio.png) | ![Caffeine with pale carbon and thin black bonds](docs/assets/screenshots/style-paton-inspired.png) |
| **Soft studio** — ambient shading | **Flat** — unshaded colors and outlines |
| ![Caffeine in Soft studio](docs/assets/screenshots/style-soft-studio.png) | ![Caffeine in Flat](docs/assets/screenshots/style-flat.png) |
| **Tube** — thick, element-colored sticks | **Ball and tube** — rounded atoms and colored bonds |
| ![Caffeine in Tube](docs/assets/screenshots/style-tube.png) | ![Caffeine in Ball and tube](docs/assets/screenshots/style-ball-and-tube.png) |
| **Wire** — thin, element-colored sticks | **vdW** — space-filling spheres |
| ![Caffeine in Wire](docs/assets/screenshots/style-wire.png) | ![Caffeine in vdW](docs/assets/screenshots/style-vdw.png) |

| Ray tracing | Optional contact lines and vdW overlay |
| --- | --- |
| ![Caffeine exported with physical ray-traced lighting](docs/assets/screenshots/ray-traced.png) | ![Illustrative water dimer with a teal contact and translucent van der Waals spheres](docs/assets/screenshots/contact-addons.png) |
| In **Figure**, set **Renderer → Ray traced · physical lighting**. This example uses 64 samples. More samples reduce noise and take longer. Ray tracing requires WebGL 2. | Under **Figure → Figure add-ons**, enable **Automatic NCI contact lines** and/or **Translucent van der Waals spheres**, then click **Fit view**. This water dimer is an illustrative geometry. |

Contact lines are suggestions based on distances and angles: teal for hydrogen
bonds, purple for halogen contacts, and gray for other close contacts. Keep
hydrogens visible for hydrogen-bond lines. They do not calculate interaction
energies or electron-density NCI surfaces; those surfaces require precomputed
cube fields. See the [rendering details and limitations](docs/USAGE.md#usage).

## More help

- [Detailed installation](docs/INSTALLATION.md): Conda, source ZIP, Git, CPU/GPU setup, repairs, and troubleshooting.
- [Using Alder](docs/USAGE.md): supported files, measurements, comparisons, surfaces, figure exports, and scientific limitations.
- [Local calculations](docs/MLIP.md) and [tested model/platform compatibility](docs/MLIP_ACCEPTANCE.md).
- [Capabilities](ALDER_CAPABILITIES.md) and [example files with source attribution](tests/data/README.md).

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
commands are in the [acceptance guide](docs/MLIP_ACCEPTANCE.md). Desktop integration
tests in `tests/*_smoke.py` require a graphical session.

Bundled renderer and editor assets are included. Editing them requires Node.js;
see [web development](web/README.md). Standalone release instructions are in the
[Windows](packaging/WINDOWS.md), [macOS](packaging/MACOS.md), and
[Linux](packaging/LINUX.md) packaging guides. The [Windows release workflow](packaging/RELEASING.md)
attaches the tested Windows installer and portable ZIP to a GitHub release draft.

To regenerate the screenshots and figures, run `python scripts/capture_readme.py`
from an installed source checkout in a graphical desktop session. Captures use
the real app, attributed fixtures in `tests/data`, and illustrative molecular
geometries; they do not download or run ML models.
