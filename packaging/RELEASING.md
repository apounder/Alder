# Publish the Windows installer from GitHub

The release workflow builds and checks Windows only. Mac and Linux users can
follow the terminal installation instructions in the README; their packaging
jobs do not block the Windows installer.

## First release, step by step

1. In **GitHub Desktop**, commit the source changes and click **Push origin**.
   Include `.github/workflows`, `packaging`, `scripts`, `src`, and `tests`.
   Do not commit `dist`, `build`, `.venv`, or `.build-tools`.
   The workflow must reach the default branch to show its Run button.
2. Open the repository on GitHub. Choose **Actions → Windows release → Run
   workflow**, select the default branch, and click **Run workflow**.
   Start a new run after pushing fixes: rerunning an old job uses its old commit.
3. Wait for **windows** and **release** to succeed. The Windows job runs tests,
   builds the executable, installs it, checks the installed app and shortcuts,
   and uninstalls it. The release job verifies the download checksums.
4. Open **Releases**. The new **draft** contains:
   - `Alder-<version>-Windows-x64-GUI-Setup.exe`
   - `Alder-<version>-Windows-x64-GUI-Portable.zip`
   - `SHA256SUMS.txt`
5. Try the installer on a Windows PC, review the notes, and click **Publish
   release**. Share the Releases link with users. Until publication, the draft
   is not a public download. The installer is unsigned.

The workflow uses GitHub's built-in token; no personal token is needed. It needs
Actions enabled and permission to create releases. Repository or organization
policies can restrict those permissions. Check a failed job's log before retrying.

For later releases, update `project.version` in `pyproject.toml`, commit and push,
then repeat. Pushing a matching version tag such as `v0.4.1` also starts the build.
Existing releases are never overwritten: use a new version, or deliberately
remove an unpublished failed draft before retrying that version.

## What users install

Setup creates the **Alder** Start-menu entry and an optional desktop shortcut.
First launch offers graphical setup for optional MLIP models, CPU/NVIDIA hardware,
and Hugging Face access. Later launches reuse installed models. Python, Git,
Conda, and terminal commands are unnecessary for the packaged Windows app.
No private model weights or access tokens are included.

The larger Windows offline CPU edition remains optional: run **Windows download**
separately with its offline checkbox selected and attach its downloads if wanted.
That individual workflow uploads temporary Actions artifacts; **Windows release**
creates the public-download draft automatically.

See [Windows packaging details](WINDOWS.md), or the terminal instructions for
[Mac](../docs/INSTALLATION.md#macos) and [Linux](../docs/INSTALLATION.md#linux).
