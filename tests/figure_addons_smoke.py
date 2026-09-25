"""Run on a desktop: python tests/figure_addons_smoke.py."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from alder.app import Window, configure_app

app = QApplication([])
configure_app(app)
errors = []
QMessageBox.warning = lambda parent, title, text: errors.append(text)


def wait(check):
    start = time.monotonic()
    while time.monotonic() - start < 60:
        app.processEvents()
        assert not errors, errors
        if check():
            return
        time.sleep(.01)
    raise AssertionError('Desktop renderer timed out')


with tempfile.TemporaryDirectory() as folder:
    os.environ['ALDER_MLIP_HOME'] = str(Path(folder) / 'app-data')
    window = Window()
    window.bridge.error.connect(errors.append)
    window.builder_bridge.error.connect(errors.append)
    window.show()

    def js(expression, builder=False):
        values = []
        web = window.builder_web if builder else window.web
        web.page().runJavaScript('JSON.stringify(' + expression + ')', values.append)
        wait(lambda: values)
        return json.loads(values[0])

    try:
        wait(lambda: window.renderer_ready and window.builder_ready)
        xyz = Path(folder) / 'contact.xyz'
        xyz.write_text('3\nHydrogen-bond example\nO 0 0 0\nH 1 0 0\nO 2.8 0 0\n')
        window.open_paths([xyz])
        wait(lambda: window.calculation is not None and not window.busy)
        window.copy_selected_geometry()
        wait(lambda: window.builder_state.get('atoms') == 3)
        for preset, representation in [('Flat', 'ball'), ('Tube', 'sticks'), ('Ball and tube', 'ball'), ('Wire', 'sticks'), ('vdW', 'space'), ('Studio', 'ball')]:
            window.preset.setCurrentText(preset)
            for builder, name in [(False, 'calculationApp'), (True, 'builderApp')]:
                wait(lambda: js(name + '.view.appearance.preset', builder) == preset)
                assert js(name + '.view.style.representation', builder) == representation
        window.auto_contacts.setChecked(True)
        window.vdw_overlay.setChecked(True)
        window.vdw_opacity.setValue(25)
        assert window.vdw_opacity.isEnabled()
        for builder, name in [(False, 'calculationApp'), (True, 'builderApp')]:
            wait(lambda: js(name + '.view.figureGroup.children.length', builder) == 2)
            assert js(name + '.view.figureAddons.opacity', builder) == .25
            assert any(c['kind'] == 'hydrogen' for c in js(name + '.view.contacts', builder))
        window.preview_builder_figure()
        assert window.builder_active
        window.export_size.setValue(400)
        path = Path(folder) / 'figure.png'
        window.render_export(path)
        wait(lambda: path.exists() and not window.exporting)
        assert path.stat().st_size > 1000
        window.auto_contacts.setChecked(False)
        window.vdw_overlay.setChecked(False)
        assert not window.vdw_opacity.isEnabled()
        for builder, name in [(False, 'calculationApp'), (True, 'builderApp')]:
            wait(lambda: js(name + '.view.figureGroup.children.length', builder) == 0)
        window.orthographic.setChecked(False)
        wait(lambda: js('!!builderApp.view.camera.isPerspectiveCamera', True))
        js('builderApp.view.fit() ?? null', True)
        original_distance = js('builderApp.view.camera.position.distanceTo(builderApp.view.controls.target)', True)
        window.vdw_overlay.setChecked(True)
        wait(lambda: js('builderApp.view.figureAddons.vdw', True))
        js('builderApp.view.fit() ?? null', True)
        assert js('builderApp.view.camera.position.distanceTo(builderApp.view.controls.target)', True) > original_distance
        print('PASS: native preset controls, shared calculation/builder add-ons, opacity, Figure export and cleanup.')
    finally:
        window.close()
        app.processEvents()
