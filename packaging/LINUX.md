# Linux desktop packages

The GitHub workflow targets **Ubuntu 24.04 and compatible newer systems**, with
separate **x64** (Intel/AMD) and **ARM64** downloads. Other distributions should
use the [source installation](../README.md#linux) unless their libraries match.
A graphical desktop session is required; these are not server applications.

## Install and open

1. Open [GitHub Releases](https://github.com/apounder/alder/releases). Download
   `Alder-<version>-Linux-x64.deb` or `Alder-<version>-Linux-arm64.deb`.
   If no matching release exists, follow the source instructions instead.
2. Open the downloaded `.deb` with your distribution's graphical package
   installer. Approve installation and the required system libraries.
   If your desktop has no graphical package installer, use a terminal in the
   download folder: `sudo apt install ./Alder-<version>-Linux-x64.deb`, replacing
   the filename with the one you downloaded.
3. Open **Alder** from your applications menu. The **Set up Alder** window
   installs your chosen optional models. Choose CPU, or NVIDIA/CUDA with a
   compatible driver. Uncheck all models to use the viewer only.
4. Open **Alder** from the same menu next time. Models remain installed.
   To add or repair models, open **Local MLIP → Environment / models → Guided setup**.

Python, Git, and Conda are included or unnecessary for this desktop package.
MLIP setup downloads separate calculation environments and weights; it needs
internet and several GB of storage. UMA requires
[Hugging Face access](../README.md#get-access-to-uma-step-by-step).

## Portable archive

Extract the complete `.tar.gz`, then open the `Alder` executable inside its
folder. Keep `_internal` beside it. Some file managers require allowing execution
in **Properties → Permissions**. This route does not add an applications-menu
entry; use the `.deb` for that integration.

Portable builds still need the host's Qt/WebEngine system libraries. On Ubuntu:

```sh
sudo apt install libegl1 libopengl0 libnss3 libnspr4 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0 libxcb-render-util0 libxcb-shape0 libxcb-randr0 libxcb-sync1 libxcb-xfixes0 libxcb-xkb1 libx11-xcb1 libsm6 libice6 libgl1 libxkbcommon-x11-0 libasound2t64 libx11-6 libxcomposite1 libxdamage1 libxrandr2 libxtst6 libxss1 libgbm1 libdrm2 libfontconfig1 libglib2.0-0t64 libdbus-1-3
```

Install desktop packages as your ordinary user through the system installer;
run the app as your ordinary user. Diagnostics go to
`~/.local/state/Alder/studio.log` (or `$XDG_STATE_HOME/Alder/studio.log`).
Uninstall with your package manager; downloaded models and user data are retained.

## Build and validate

For normal installation, use the [Linux terminal walkthrough](../README.md#linux).
Experimental packages can be built with **Actions → Linux download → Run workflow**.
These builds are separate from the Windows release.
Both architectures run the tests, build a relocatable executable, launch it from
a path with spaces and Unicode, install the `.deb`, verify the menu entry and
installed executable, and uninstall it. Assets upload only after those checks pass.

For a local build, use an Ubuntu 24.04 machine of the target architecture, Python
3.14, Git, the libraries above, and `dpkg-dev`. In a virtual environment:

```sh
python -m pip install -r packaging/linux-requirements.txt ".[dev]"
python scripts/build_linux.py
```

Downloads and checksums appear in `dist/release`. A build made on a newer Linux
system may require newer libraries; do not distribute it as an Ubuntu 24.04
build. Use the GitHub runners for the declared baseline. Linux and Mac binaries
cannot be produced by the Windows installer builder.
