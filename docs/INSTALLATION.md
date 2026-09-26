# Detailed installation and model setup

[Back to the quick start](../README.md#desktop-downloads) · [Screenshot tour](../README.md#interface-and-results)

## Installation

For the fewest steps, use a published [desktop download](#1-desktop-download).
For installation from the repository, follow the complete terminal walkthrough for
[Windows](#windows), [macOS](#macos), or
[Linux](#linux), including prerequisites, setup prompts, and later launches.

Choose one route below. Each installs the desktop app and provides a walkthrough
for model selection, CPU/GPU setup, and any required Hugging Face access.
Calculation environments and downloaded models are saved for future launches.

| How you want to install | Start here | What you need first |
| --- | --- | --- |
| Clone with Git | [Windows or Mac terminal walkthrough](#4-git-clone) | Git and Python 3.11 or newer |
| You already use Anaconda or Miniforge | [Conda](#2-conda) | Conda and an extracted or cloned copy of this repository |
| Download GitHub's source ZIP | [Source ZIP](#3-source-zip) | Python 3.11 or newer and Git (for a dependency) |
| Download a desktop app | [Windows installer](#1-desktop-download) | A matching release, when available |

For first-time model setup, use an internet connection and allow several GB of
free disk space per calculator. CUDA packages need additional space. Public
AIMNet2 and MACE-ANI-CC models need no account. UMA requires Hugging Face access;
MACE-OFF23 requires licence acknowledgement.

“All models” means the supported catalogue: four AIMNet2 checkpoints, MACE-ANI-CC,
three MACE-OFF23 sizes, and UMA-s-1p2. Other MLIP families need an integration;
arbitrary Hugging Face models are not automatically compatible.

### 1. Desktop download

The GitHub source tree does not contain `dist`: that folder is ignored local
build output. The [Windows release workflow](../packaging/RELEASING.md) attaches
tested installers to a release draft; a maintainer publishes it for public access.
Cloning the repository does not download an EXE.

Download the Windows installer from the
[Alder-v1.0 prerelease](https://github.com/apounder/Alder/releases/tag/Alder-v1.0).
A source ZIP is not a desktop installer.

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

For Mac and Linux, use the [macOS terminal walkthrough](#macos) or
[Linux terminal walkthrough](#linux). These install and launch the
same GUI. Native Mac/Linux packages remain experimental developer builds and
are not required for the Windows release.

Windows builds are unsigned.

### 2. Conda

For Windows, start with the [complete Conda walkthrough](#windows-with-conda).
It covers installing Conda, downloading a source ZIP, finding its folder in
Anaconda/Miniforge Prompt, setup choices, and later launches. The ZIP route needs
no separate Python or Git installation: `environment.yml` installs both.

Download this repository using **Code → Download ZIP** and extract it, or clone it
with Git. Open Anaconda Prompt or a terminal where `conda` works, then change to
the extracted `alder` or `alder-main` folder.

Run these commands one at a time; continue after each succeeds:

```sh
conda env create -f environment.yml
conda activate alder
alder-setup --launch
```

The first command installs Python, Git, and the desktop dependencies in their own
environment. The last command walks through all selected model installations.
Enter `none` for the viewer only; Alder opens after successful setup. Use these
Conda commands throughout this route; `install.py` would create a separate `.venv`.
There is no need to find model Python paths or install PyTorch yourself.

Setup creates **Alder Source**: a Windows Start-menu/desktop shortcut, a Mac app
in your home **Applications** folder, or a Linux applications-menu entry. Open it
for later launches without a terminal. Keep the Conda environment installed.
The terminal alternative remains:

```sh
conda activate alder
alder
```

If you already created this Conda environment using the previous instructions,
update the app from the repository folder and start the new walkthrough:

```sh
conda activate alder
python -m pip install --upgrade .
alder-setup --launch
```

This route uses the repository's `environment.yml`. A published
`conda install alder` package is not currently provided.

If environment creation reports that `alder` already exists, use
`conda activate alder` and the update commands above from the source folder.
If creation was interrupted before dependencies finished installing, return to
that folder and run `conda env update -n alder -f environment.yml`, then activate
it and rerun `alder-setup --launch`.

If `alder` or `alder-setup` is not recognized after activation, try
`python -m alder` or `python -m alder setup --launch`, respectively. If Python
reports `No module named alder`, return to the source folder and run
`python -m pip install .` in the activated environment before retrying.

For Windows `conda` or activation errors, reopen **Anaconda Prompt** or
**Miniforge Prompt** from Start. These instructions use that prompt's `cd /d`
and `%USERPROFILE%` syntax; the PowerShell route uses different commands.

### 3. Source ZIP

1. Complete the prerequisite steps for [Windows](#windows) or
   [macOS](#macos): Python 3.11 or newer and Git. The pinned cclib
   parser needs Git even when Alder itself comes from a ZIP. Conda is an alternative
   if you prefer not to install these prerequisites separately.
2. Check `python --version` on Windows or `python3 --version` on macOS/Linux,
   and `git --version`. Continue when both work and Python is at least 3.11.
3. On the GitHub repository page, choose **Code → Download ZIP**, then extract it.
4. Open a terminal in the extracted folder containing `install.py`. In Windows
   File Explorer, open that folder, type `powershell` into the address bar, and
   press Enter. On Mac, open Terminal, type `cd ` (with a space), drag the extracted
   folder from Finder into Terminal, and press Return.
5. Run the command for your operating system, then follow the
   [terminal setup prompts](#finish-the-terminal-setup).

Windows:

```powershell
python install.py --launch
```

macOS:

```sh
python3 install.py --device cpu --launch
```

Linux: use `python3 install.py --launch`.
Setup creates a local `.venv`, downloads a suitable app Python when needed,
installs the desktop dependencies, and starts the model walkthrough. You do not
need to activate `.venv`. The pinned cclib source is downloaded automatically
using Git. Node.js and npm are not needed for this route.

Setup also creates an **Alder Source** launcher (Start/desktop on Windows, home
Applications on Mac, applications menu on Linux). Open that launcher next time;
keep the source folder and `.venv` in place. To launch from a terminal on Windows:

```powershell
.\.venv\Scripts\python.exe -m alder
```

Or on macOS/Linux:

```sh
./.venv/bin/python -m alder
```

### 4. Git clone

Use the platform-specific commands in the README:

- [Windows: PowerShell](#windows).
- [macOS: Terminal](#macos).
- [Linux: Terminal](#linux).

These cover prerequisites, cloning, `install.py`, setup, and later launches.
Cloning downloads the source; it does not install Alder or produce an EXE/DMG.
Keep the checkout and its `.venv` folder. Setup creates **Alder Source** shortcuts
using that environment; it does not compile a redistributable installer. Pass
`--no-shortcuts` to skip launcher creation. If creation fails, setup prints a
warning and the terminal launch commands still work. Rerun setup after correcting
the permissions or moving the environment to recreate the launcher.

## Terminal walkthroughs

Use these steps for Mac, Linux, or an alternative Windows source installation.
Windows users can also use the [published installer](#1-desktop-download).

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
   Store instead, resolve that before continuing; see [troubleshooting](INSTALLATION.md#common-setup-problems).
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
redistributable Setup.exe; use the [Windows release workflow](../packaging/RELEASING.md) to build installers.

You can launch from any folder after activating the environment. To add models
later, use **Local MLIP → Environment / models → Guided setup**, or close Alder
and run `alder-setup --launch` in the activated environment. For updates or an
existing `alder` environment, see the [Conda maintenance instructions](INSTALLATION.md#2-conda).

### macOS

The Mac runtime remains experimental and has not been validated on a Mac in this
project's [test record](MLIP_ACCEPTANCE.md). These instructions install from
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
and the [troubleshooting guide](INSTALLATION.md#common-setup-problems).

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
| **Model access/licence questions** | Only appear for selected restricted models. Read their terms first. UMA also needs [Hugging Face approval and a read token](../README.md#get-access-to-uma-step-by-step); pasted tokens stay hidden in the terminal. Public models need no login. |
| **Continue with setup? yes/no** | Enter `yes`. Optional model downloads can require several GB. Wait for installation and verification to finish. |

The `--launch` option opens Alder when setup succeeds. Start with
[Open your first file](../README.md#open-your-first-file) below. If setup reports an error,
read the first error and use [troubleshooting](INSTALLATION.md#common-setup-problems)
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

For a source ZIP instead of Git, follow the [ZIP instructions](INSTALLATION.md#3-source-zip).
For repairs, checks, or updates, see [ongoing setup](INSTALLATION.md#add-models-repair-or-resume-later).


## The setup walkthrough

The terminal and desktop walkthroughs use the same setup code and model cache.
For the exact text prompts and first-time choices, see
[Finish the terminal setup](#finish-the-terminal-setup).

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
results and remaining limits are listed in [MLIP acceptance](MLIP_ACCEPTANCE.md).

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

**Update a cloned copy:** close Alder, open a terminal in its checkout, and run
`git pull --ff-only`. Then rerun `python install.py --launch` on Windows or
`python3 install.py --device cpu --launch` on macOS. The installer updates the app
in its existing `.venv`; verified models are reused. If Git reports local changes
or a divergent branch, resolve those before updating rather than deleting your work.
Source ZIP users should extract the new source into a new folder and install it
there; do not copy `.venv` between folders or operating systems.

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
| `python` opens the Microsoft Store on Windows | Finish installing Python from python.org and reopen PowerShell. Follow [Python's Windows command troubleshooting](https://docs.python.org/3/using/windows.html#troubleshooting) if the command still launches the Store; verify `python --version` before continuing. |
| Mac `python3 --version` is older than 3.11 | Install a current Python from python.org, reopen Terminal, and check again. Do not replace or remove Apple's system Python. |
| Mac reports a certificate verification error | For a python.org installation, run **Applications → Python 3.x → Install Certificates.command** for the version used to start setup, then retry. See [Python's Mac installation steps](https://docs.python.org/3/using/mac.html#installation-steps). |
| Mac asks for Command Line Tools when running Git | Finish the macOS installer before running the clone command. If needed, start it with `xcode-select --install`. |
| `destination path 'alder' already exists` | If it is your existing checkout, enter it and run the install command there. Otherwise, choose another parent folder for the clone and use that location for later launches. |
| `can't open file 'install.py'` | Change into the cloned or extracted folder containing `install.py`, then rerun the command. |
| `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python` (Mac/Linux) does not exist | Check that you are in the right `alder` folder. If so, installation did not finish: rerun the platform's `install.py` command and resolve its first error. |
| No Alder entry in Start or Applications after source installation | Expected: launch it with the platform's `.venv` command in the README. Only a separate packaged desktop installer provides the desktop app installation. |
| GPU detected but CUDA check fails | Update the NVIDIA driver, reopen Guided setup and choose CUDA/Repair; CPU is also available. |
| Hugging Face returns access denied | Check model approval and token permissions; a valid token alone is not approval. Other public models do not need it. |
| An interrupted or failed model installation | Rerun setup; use Repair for a damaged environment or checksum failure. Keep the cached models and job folder. |
