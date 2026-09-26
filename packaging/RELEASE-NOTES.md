Download the installer for your computer from **Assets** below. Python, Git,
Conda, and Node.js are not needed to run these desktop downloads.

| Computer | Download | Open again later |
| --- | --- | --- |
| Windows x64 | `Windows-x64-GUI-Setup.exe` | Alder in the Start menu or the optional desktop shortcut |
| Mac with Apple Silicon | `macOS-AppleSilicon.dmg` — drag Alder to Applications | Alder in Applications |
| Intel Mac | `macOS-Intel.dmg` — drag Alder to Applications | Alder in Applications |
| Ubuntu 24.04 or compatible newer Linux, Intel/AMD | `Linux-x64.deb` — open with your graphical package installer | Alder in the applications menu |
| Ubuntu 24.04 or compatible newer Linux, ARM64 | `Linux-arm64.deb` | Alder in the applications menu |

Portable ZIPs and Linux tar archives contain the same app. Extract the complete
folder before opening Alder; keep its bundled files beside the executable.

First launch opens **Set up Alder**. Leave every model unchecked for the viewer
only, or select models and CPU/NVIDIA hardware. Setup downloads and verifies
optional calculation environments. Later, use **Local MLIP → Environment / models
→ Guided setup** to add or repair models. Cached models are reused.

UMA needs your approved Hugging Face account and a read token. MACE-OFF23 needs
licence acknowledgement. Public AIMNet2 and MACE-ANI-CC need no account. Model
access is separate from installing Alder; these GUI packages do not bundle weights.

Windows builds are unsigned. Mac builds require macOS 15+, are ad-hoc signed,
and are not Apple-notarized. For a trusted Mac download blocked on first launch,
use System Settings → Privacy & Security → Open Anyway. CPU is the Mac calculation
backend; Apple GPU acceleration is not implemented.

Maintainer: this release is created as a draft after all build and packaged-app
checks pass. Review the platform reports and try the downloaded installers before
publishing. SHA256SUMS.txt covers every attached installer and portable archive.
