# Publish desktop downloads from GitHub

This builds the Windows installer, both Mac apps, and both Linux packages on
GitHub's own computers. Users download the finished files from **Releases**;
they do not need to clone the repository or install Python.

## First release, step by step

1. In **GitHub Desktop**, commit the source changes and click **Push origin**.
   Include the new `.github/workflows`, `packaging`, `scripts`, `src`, and `tests`
   files. Do not commit `dist`, `build`, `.venv`, or `.build-tools`.
   The workflow must reach the repository's default branch to show its Run button.
2. Open the repository on GitHub. Choose **Actions → Desktop release → Run
   workflow**, select the default branch, and click **Run workflow**.
3. Wait for every platform and the final **release** job to succeed. Builds run
   tests and launch the packaged apps before uploading their downloads. The
   final job checks the checksums and requires all five native installers.
4. Open **Releases**. There will be a **draft** named for the version in
   `pyproject.toml`, with installers, portable archives, and `SHA256SUMS.txt`
   already attached. Download and try the installers on the intended computers.
   Windows is unsigned and macOS is not notarized; see their packaging guides.
   Mark the first release **pre-release** while Mac validation is pending.
5. Review the release notes and click **Publish release**. Share the Releases
   link with users. Until this step, the draft is not a public download.

The workflow uses GitHub's built-in token; no personal token is needed. It needs
Actions enabled and permission to create releases. Repository or organization
policies can restrict those permissions. Check a failed job's log before retrying.

For later releases, change `project.version` in `pyproject.toml`, commit and push,
then repeat. Pushing a matching tag such as `v0.4.1` also starts the workflow.
Existing releases are never overwritten: use a new version, or remove an
unpublished failed draft deliberately before retrying that version.

## What users receive

| Platform | Installer | Portable alternative |
| --- | --- | --- |
| Windows x64 | `Alder-<version>-Windows-x64-GUI-Setup.exe` | `…-Portable.zip` |
| macOS Apple Silicon | `Alder-<version>-macOS-AppleSilicon.dmg` | App ZIP |
| macOS Intel | `Alder-<version>-macOS-Intel.dmg` | App ZIP |
| Linux x64 | `Alder-<version>-Linux-x64.deb` | `.tar.gz` |
| Linux ARM64 | `Alder-<version>-Linux-arm64.deb` | `.tar.gz` |

All editions include the viewer and graphical model setup. First launch offers
optional online MLIP installation and explains Hugging Face access. Subsequent
launches reuse installed models. No model token or private weights are bundled.
The larger Windows offline CPU edition is optional: run **Windows download**
separately with its offline checkbox selected, then attach its downloads if wanted.

Individual **Windows download**, **macOS download**, and **Linux download** runs
produce temporary Actions artifacts without creating a release. Use **Desktop
release** for the complete draft. A source ZIP or `git clone` contains no prebuilt
installer; its setup command instead creates an **Alder Source** launcher.

Platform details: [Windows](WINDOWS.md), [macOS](MACOS.md), [Linux](LINUX.md).
