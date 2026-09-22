"""One-folder distribution: Python, Qt WebEngine, chemistry, and offline assets."""
from pathlib import Path
import sys
import tomllib
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_delvewheel_libs_directory

root = Path(SPECPATH).parent
assets = root / 'src' / 'molecule_studio' / 'assets'
datas, binaries = collect_delvewheel_libs_directory(
    'rdkit',
    datas=[(str(assets), 'molecule_studio/assets')] + collect_data_files('rdkit', includes=['Data/**']),
    binaries=collect_dynamic_libs('rdkit'),
)
macos = sys.platform == 'darwin'
if macos:
    # Collected before signing, so the final bundle's resource seal stays valid.
    datas += [(str(root / 'build' / 'macos-notices'), 'ReleaseNotes')]
a = Analysis(
    [str(root / 'run_studio.py')],
    pathex=[str(root / 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={'matplotlib': {'backends': ['QtAgg']}},
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'IPython', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='MoleculeStudio', console=False, debug=False, strip=False, upx=False,
    icon=str(assets / ('studio.icns' if macos else 'studio.ico')),
    argv_emulation=False,
    entitlements_file=str(root / 'packaging' / 'macos-entitlements.plist') if macos else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MoleculeStudio')
if macos:
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    app = BUNDLE(
        coll, name='Molecule Studio.app', icon=str(assets / 'studio.icns'),
        bundle_identifier='org.moleculestudio.desktop', version=version,
        info_plist={
            'CFBundleVersion': version,
            'LSMinimumSystemVersion': '15.0',
            'NSHighResolutionCapable': True,
            'NSPrincipalClass': 'NSApplication',
            'NSSupportsAutomaticGraphicsSwitching': True,
        },
    )
