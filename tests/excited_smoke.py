"""Desktop import, UV controls, exports, and coexistence with vibrations."""
import csv
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from alder.app import Window, configure_app

app = QApplication([])
configure_app(app)
w = Window()
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
w.show()
errors = []
w.bridge.error.connect(errors.append)
w.builder_bridge.error.connect(errors.append)
QMessageBox.warning = lambda parent, title, message: errors.append(str(message))


def wait(check, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        assert not errors, errors
        if check():
            return
        time.sleep(.02)
    raise AssertionError('Timed out: ' + w.statusBar().currentMessage())


def js(code):
    values = []
    w.web.page().runJavaScript(code, values.append)
    wait(lambda: bool(values))
    return values[0]


try:
    wait(lambda: w.renderer_ready and w.builder_ready)
    panel = w.uv_panel
    assert panel.table.rowCount() == 0 and not panel.transitions_export.isEnabled()
    for name, count in [('gaussian-td.log', 5), ('orca-td.out', 10), ('orca6-td.out', 10),
                        ('gaussian-cis.log', 10), ('gaussian-eomccsd.log', 10), ('orca6-adc2.out', 2)]:
        w.open_paths([Path(__file__).parent / 'data' / name])
        wait(lambda: not w.busy)
        wait(lambda: js('window.sceneState.atoms') == len(w.calculation.atomnos))
        assert panel.table.rowCount() == count
        assert w.results.currentIndex() == w.uv_tab
        assert float(panel.table.item(0, 2).text()) == round(w.calculation.transitions.energies[0], 4)
        print('PASS UV import and geometry: ' + name, flush=True)
    t = panel.transitions
    for unit in ('nm', 'eV', 'cm⁻¹'):
        panel.units.setCurrentText(unit)
        panel.clicked(SimpleNamespace(inaxes=panel.stick_ax, xdata=float(t.positions(unit)[1])))
        assert panel.table.currentRow() == 1
    panel.shape.setCurrentText('Lorentzian')
    panel.width.setValue(.5)
    panel.normalize.setChecked(False)
    panel.sticks.setChecked(False)
    assert not panel.stick_ax.get_visible()
    x, y = panel.curve()
    assert len(x) == 2400 and np.isfinite(y).all()
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        save = QFileDialog.getSaveFileName
        try:
            for button, filename in [(panel.transitions_export, 'states.csv'), (panel.curve_export, 'curve.csv')]:
                QFileDialog.getSaveFileName = lambda *a, **k: (str(folder / filename), 'CSV (*.csv)')
                button.click()
            rows = list(csv.DictReader((folder / 'states.csv').open()))
            assert len(rows) == 2 and float(rows[0]['oscillator_strength']) == t.strengths[0]
            curve = list(csv.DictReader((folder / 'curve.csv').open()))
            np.testing.assert_allclose([float(r['oscillator_strength_density_per_eV']) for r in curve], y)
            assert curve[0]['shape'] == 'Lorentzian' and float(curve[0]['FWHM_eV']) == .5
            for extension in ('png', 'svg', 'pdf'):
                path = folder / ('spectrum.' + extension)
                QFileDialog.getSaveFileName = lambda *a, **k: (str(path), '')
                panel.toolbar.save_figure()
                assert path.stat().st_size > 1000
            with Image.open(folder / 'spectrum.png') as image:
                assert image.width > 200 and image.height > 100
        finally:
            QFileDialog.getSaveFileName = save
    print('PASS unit conversion, selection, width/shape controls, CSV and toolbar PNG/SVG/PDF export', flush=True)
    panel.units.setCurrentText('nm')
    panel.normalize.setChecked(True)
    panel.sticks.setChecked(True)
    panel.shape.setCurrentText('Gaussian')
    panel.width.setValue(.3)
    w.grab().save(str(Path(tempfile.gettempdir()) / 'alder-uv.png'))
    for strengths, expected in [(np.full(2, np.nan), 'missing'), (np.zeros(2), 'zero')]:
        panel.set_calculation(replace(w.calculation, transitions=replace(t, strengths=strengths)))
        assert expected in panel.note.text()
        assert panel.table.item(0, 4).text() == ('—' if expected == 'missing' else '0.000000')
    w.open_paths([Path(__file__).parent / 'data' / 'gaussian-freq.log'])
    wait(lambda: not w.busy)
    assert panel.table.rowCount() == 0 and not panel.curve_export.isEnabled()
    w.results.setCurrentIndex(w.vibration_tab)
    wait(lambda: w.vib_play.isEnabled())
    w.vib_play.click()
    assert w.vib_play.isChecked()
    w.results.setCurrentIndex(w.uv_tab)
    assert not w.vib_play.isChecked() and not w.vibration_preview
    print('PASS missing/zero data, clearing previous spectra, and vibration playback switching', flush=True)
    assert not errors, errors
finally:
    w.close()
    app.processEvents()
