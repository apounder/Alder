"""One-folder distribution: Python, Qt WebEngine, chemistry, and offline assets."""
from pathlib import Path
import sys
import tomllib
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_delvewheel_libs_directory

root = Path(SPECPATH).parent
assets = root / 'src' / 'alder' / 'assets'
worker_source = root / 'src' / 'alder' / 'mlip'
worker_data = [(str(p), 'alder/mlip/' + str(p.parent.relative_to(worker_source)))
               for p in worker_source.rglob('*') if p.is_file() and p.suffix in {'.py', '.json'}]
datas, binaries = collect_delvewheel_libs_directory(
    'rdkit',
    datas=[(str(assets), 'alder/assets')] + worker_data + collect_data_files('rdkit', includes=['Data/**']),
    binaries=collect_dynamic_libs('rdkit'),
)
macos = sys.platform == 'darwin'
if macos:
    # Collected before signing, so the final bundle's resource seal stays valid.
    datas += [(str(root / 'build' / 'macos-notices'), 'ReleaseNotes')]
a = Analysis(
    [str(root / 'run_alder.py')],
    pathex=[str(root / 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={'matplotlib': {'backends': ['QtAgg']}},
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'IPython', 'pytest', 'torch', 'fairchem', 'mace', 'aimnet', 'sella', 'jax'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='Alder', console=False, debug=False, strip=False, upx=False,
    icon=str(assets / ('alder.icns' if macos else 'alder.ico')),
    argv_emulation=False,
    entitlements_file=str(root / 'packaging' / 'macos-entitlements.plist') if macos else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Alder')
if macos:
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    app = BUNDLE(
        coll, name='Alder.app', icon=str(assets / 'alder.icns'),
        bundle_identifier='org.alder.desktop', version=version,
        info_plist={
            'CFBundleVersion': version,
            'LSMinimumSystemVersion': '15.0',
            'NSHighResolutionCapable': True,
            'NSPrincipalClass': 'NSApplication',
            'NSSupportsAutomaticGraphicsSwitching': True,
        },
    )
