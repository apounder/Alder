# Detailed installation and model setup

[Back to the quick start](../README.md#installation) · [Screenshot tour](../README.md#interface-and-results)

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
[macOS guide](../packaging/MACOS.md) for current validation and first-launch details.
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

