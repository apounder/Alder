# macOS releases

Status: experimental packaging; macOS validation is pending. Run both
architecture jobs and test the downloaded application on a Mac before a
general release.

## Build with GitHub Actions

1. In GitHub Desktop, open the repository, commit the changes, and choose
   **Push origin**. If starting a new repository instead, choose
   **Publish repository** after the first commit. Include `.github`, `packaging`, `scripts`,
   `src`, `web`, `tests`, `pyproject.toml`, and `run_studio.py`. Build folders and
   local calculation examples are ignored. No Mac, npm, or terminal is needed
   for these steps.
2. On the repository's GitHub page, choose **Actions → macOS download → Run
   workflow**. The workflow must be on the default branch. It uses GitHub's
   `macos-15` Apple Silicon and `macos-15-intel` runners separately.
3. Wait for both jobs to turn green. Download the **MoleculeStudio-macOS-AppleSilicon**
   and **MoleculeStudio-macOS-Intel** artifacts from the completed run. Each
   artifact ZIP contains a DMG, an app ZIP, and SHA-256 checksums. Actions
   downloads require a GitHub login and expire after 30 days.
4. To make lasting public downloads, attach the DMGs, app ZIPs, and checksum
   files to a GitHub Release. Mark the initial Mac release as a **pre-release**
   until someone has tried it on a real Mac. The workflow does not publish
   releases automatically or need repository write permissions.

GitHub also runs checks for pull requests and version tags. Standard hosted
runners are free for public repositories; private repositories use the
account's Actions allowance and billing settings. Never upload `.venv`,
`node_modules`, signing credentials, or build output into source control.

## Downloads and installation

The initial target is **macOS 15 (Sequoia) and newer**. Older macOS versions are
not claimed as supported. These are separate native apps, not a universal app.

| Mac | Download |
| --- | --- |
| Apple M-series chip | `MoleculeStudio-0.2.0-macOS-AppleSilicon.dmg` |
| Intel processor | `MoleculeStudio-0.2.0-macOS-Intel.dmg` |

Open the DMG, drag **Molecule Studio** onto **Applications**, eject the DMG,
then open the app from Applications. The alternative ZIP contains the same
`.app`; extract it and move it to Applications. Python, Node.js, npm, a browser,
and localhost are not needed. The calculation viewer, both builders, fragments,
WASM, surfaces, and figure renderer are bundled for offline use. Open files
inside the app or drop them onto its window; no file associations are installed.

## Signing and the first launch

The initial build is **ad-hoc signed**, which lets the bundled binaries run on
Apple Silicon. It is **not Developer ID signed or notarized by Apple**. The
automated signature check verifies bundle integrity, not Gatekeeper approval.
macOS may block a downloaded copy. For a trusted copy, attempt to open it,
then use **System Settings → Privacy & Security → Open Anyway** and confirm.
Managed Macs may prohibit this exception. See [Apple's instructions](https://support.apple.com/en-us/102445).
Do not disable Gatekeeper or use a blanket quarantine-removal command.

For an ordinary public release without an unidentified-developer exception,
the publisher must configure an Apple Developer ID certificate and Apple's
notarization service. Those credentials are not configured here; this workflow
does not submit files to Apple. A green Actions result cannot substitute for
testing a downloaded, quarantined app on another Mac.

## What the workflow checks

Both architectures run the parser/native-chemistry tests and actual desktop
fragment insertion tests, including the C–H hydrogen fix. The build script:

- Packages a native `.app` with the Studio icon, macOS metadata, dependency
  notices, and the entitlements required by Qt WebEngine's JavaScript/WASM engine.
- Validates its architecture and nested signatures, builds a DMG with an
  Applications shortcut, and archives the app with macOS `ditto` to preserve
  framework symlinks and permissions.
- Mounts the DMG, copies the app into a temporary Applications folder with
  spaces and a non-ASCII character in its path, then ejects the DMG.
- Launches the copied app through LaunchServices, with developer Python/Qt
  paths removed. The app's self-check blocks HTTP/HTTPS and checks Gaussian/ORCA
  imports, orbital/frequency data, both renderers, offline WASM SMILES, 2D
  drawing, native 2D-to-3D conversion, MOL export, and a transparent PNG.
- Extracts the app ZIP and verifies its signature, then writes checksums.

The workflow uses Qt's native macOS graphics backend and fails if it cannot
render on the runner. No renderer tests are silently skipped. Rotation,
trackpad gestures, vibration playback, surfaces, Retina display scaling, and
Gatekeeper behavior still need a human check on a physical Mac.

Intel Macs use **RDKit 2025.3.6**, the available Intel macOS wheel; **RDKit
2026.3.6** does not publish Intel Mac wheels. Apple Silicon and Windows retain
2026.3.6. Both run the same stereochemistry/geometry tests, but generated
conformer coordinates can differ between versions. The bundled JS engine and
prepared fragment library are identical on both architectures.

If a job fails, download its **macOS-…-diagnostics** artifact and inspect the
workflow log. Startup output is in `~/Library/Logs/Molecule Studio/studio.log`;
the smoke report records the first exception and the checks that completed.

## Local builds on a Mac (maintainers only)

Install Python 3.14 for the Mac's native architecture and the Xcode command-line
tools. In a clean virtual environment:

```bash
python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install -r packaging/macos-requirements.txt ".[dev]"
python -m pytest -q
python scripts/build_macos.py
```

Output goes into `dist/release`. The script cannot create Mac executables on
Windows or Linux. Building directly from the spec is not the supported release
path: the script first prepares the notices that are sealed into the signed app.

References: [GitHub Mac runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[PyInstaller macOS bundles and signing](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing),
[Qt WebEngine deployment](https://doc.qt.io/qt-6/qtwebengine-deploying.html),
[Intel RDKit release files](https://pypi.org/project/rdkit/2025.3.6/#files).
