"""Regenerate README screenshots with an installed Alder environment and a desktop.

Run from the repository root: python scripts/capture_readme.py
Uses real cclib fixtures; illustrative caffeine geometry comes from RDKit.
No model downloads or calculations are started.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from rdkit import Chem
from rdkit.Chem import AllChem

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from alder.app import Window, configure_app
from alder.setup_ui import SetupWizard

OUTPUT = ROOT / 'docs/assets/screenshots'
OUTPUT.mkdir(parents=True, exist_ok=True)
app = QApplication([])
configure_app(app)
errors = []
QMessageBox.warning = lambda parent, title, message: errors.append(message)


def pump(seconds=.5):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        app.processEvents()
        assert not errors, errors
        time.sleep(.01)


def wait(check, timeout=120):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if check():
            return
        pump(.02)
    raise AssertionError('Capture timed out: ' + window.statusBar().currentMessage())


def js(expression, builder=False):
    values = []
    web = window.builder_web if builder else window.web
    web.page().runJavaScript('JSON.stringify(' + expression + ')', values.append)
    wait(lambda: values)
    return json.loads(values[0]) if values[0] else None


def capture(name, widget):
    pump(1)
    assert widget.grab().save(str(OUTPUT / (name + '.png')))
    print('Captured ' + name, flush=True)


def load(path):
    window.inspector.setCurrentIndex(0)
    window.open_paths([path])
    wait(lambda: not window.busy and window.calculation is not None and window.calculation.name == path.name)
    wait(lambda: js('calculationApp.view.model.atoms.length') == len(window.calculation.atomnos))
    pump()


def export(name):
    path = OUTPUT / (name + '.png')
    path.unlink(missing_ok=True)
    window.render_export(path)
    wait(lambda: path.exists() and not window.exporting, timeout=240)
    assert path.stat().st_size > 1000
    print('Exported ' + name, flush=True)


with tempfile.TemporaryDirectory() as folder:
    os.environ['ALDER_MLIP_HOME'] = str(Path(folder) / 'app-data')
    window = Window()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1440, 960)
    window.bridge.error.connect(errors.append)
    window.builder_bridge.error.connect(errors.append)
    window.show()
    try:
        wait(lambda: window.renderer_ready and window.builder_ready)
        window.body.widget(1).setSizes([460, 400])
        load(ROOT / 'tests/data/gaussian-opt.log')
        window.slider.setValue(2)
        capture('overview', window)
        for index, name in [(0, 'energy-profile'), (1, 'step-data')]:
            window.results.setCurrentIndex(index)
            capture(name, window.results)
        load(ROOT / 'tests/data/gaussian-freq.log')
        window.results.setCurrentIndex(2)
        window.orbital_table.selectRow(34)
        window.orbital_table.scrollToItem(window.orbital_table.item(30, 0))
        capture('orbital-levels', window.results)
        window.results.setCurrentIndex(window.vibration_tab)
        window.vibration_table.selectRow(10)
        capture('vibrations', window.results)
        load(ROOT / 'tests/data/gaussian-td.log')
        window.results.setCurrentIndex(window.uv_tab)
        capture('uv-vis', window.results)
        load(ROOT / 'tests/data/gaussian-scan2d.log')
        window.results.setCurrentIndex(window.path_tab)
        window.path_panel.table.selectRow(0)
        window.path_panel.table.scrollToTop()
        capture('scan-map', window.results)

        wizard = SetupWizard(window)
        wizard.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        wizard.show()
        capture('setup', wizard)
        wizard.close()

        molecule = Chem.AddHs(Chem.MolFromSmiles('Cn1c(=O)c2c(ncn2C)n(C)c1=O'))
        assert AllChem.EmbedMolecule(molecule, randomSeed=42) == 0
        AllChem.MMFFOptimizeMolecule(molecule)
        caffeine = Path(folder) / 'caffeine.mol'
        Chem.MolToMolFile(molecule, str(caffeine))
        window.open_paths([caffeine])
        wait(lambda: not window.busy and window.builder_state.get('atoms') == molecule.GetNumAtoms())
        assert sum(bond['order'] == 2 for bond in window.builder_model['bonds']) >= 4
        capture('builder', window)
        window.preview_builder_figure()
        pump()
        window.export_size.setValue(800)
        window.export_samples.setCurrentIndex(0)
        window.transparent.setChecked(False)
        for preset in ['Studio', 'Paton-inspired', 'Soft studio', 'Flat', 'Tube', 'Ball and tube', 'Wire', 'vdW']:
            window.preset.setCurrentText(preset)
            wait(lambda: js('builderApp.view.appearance.preset', True) == preset)
            window.send(type='fit')
            pump()
            export('style-' + preset.lower().replace(' ', '-'))
        window.preset.setCurrentText('Studio')
        window.send(type='fit')
        window.export_engine.setCurrentIndex(1)
        window.ray_samples.setValue(64)
        pump()
        export('ray-traced')
        window.export_engine.setCurrentIndex(0)

        dimer = Path(folder) / 'water-dimer.xyz'
        dimer.write_text('6\nIllustrative water dimer; not an optimized calculation\nO 0 0 0\nH .96 0 0\nH -.24 .93 0\nO 2.8 0 0\nH 3.04 .93 0\nH 3.04 -.46 .81\n')
        load(dimer)
        window.copy_selected_geometry()
        wait(lambda: window.builder_state.get('atoms') == 6)
        window.preview_builder_figure()
        window.auto_contacts.setChecked(True)
        window.vdw_overlay.setChecked(True)
        window.vdw_opacity.setValue(18)
        wait(lambda: js('builderApp.view.figureGroup.children.length', True) == 2)
        assert any(contact['kind'] == 'hydrogen' for contact in js('builderApp.view.contacts', True))
        window.send(type='fit')
        pump()
        export('contact-addons')
        assert not errors, errors
        print('PASS: all README screenshots and figures captured.', flush=True)
    finally:
        window.close()
        app.processEvents()
