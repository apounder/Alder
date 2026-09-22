"""Native IRC/scan maps, point selection, playback, and CSV/figure export."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from molecule_studio.app import Window, configure_app

app = QApplication([])
configure_app(app)
w = Window()
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
w.show()
errors = []
w.bridge.error.connect(errors.append)
QMessageBox.warning = lambda parent, title, message: errors.append(str(message))


def wait(check, timeout=90):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        app.processEvents()
        assert not errors, errors
        if check():
            return
        time.sleep(.02)
    raise AssertionError(w.statusBar().currentMessage())


def js(code):
    values = []
    w.web.page().runJavaScript(code, values.append)
    wait(lambda: bool(values))
    return values[0]


try:
    wait(lambda: w.renderer_ready and w.builder_ready)
    panel = w.path_panel
    for name in ('gaussian-scan2d.log', 'orca6-scan-relaxed.out', 'gaussian-irc-path.out'):
        w.open_paths([Path(__file__).parent/'data'/name])
        wait(lambda: not w.busy)
        wait(lambda: js('window.sceneState.atoms') == len(w.calculation.atomnos))
        p = w.calculation.reaction_path
        assert w.results.currentIndex() == w.path_tab and panel.table.rowCount() == len(p.energies)
        for index in (0, len(p.energies)//2, len(p.energies)-1):
            xy = p.parameters[index]
            panel.clicked(SimpleNamespace(inaxes=panel.ax, xdata=float(xy[0]), ydata=float(xy[1]) if len(xy) == 2 else 0))
            assert panel.table.currentRow() == index and w.step == p.steps[index], (name, index, panel.table.currentRow(), w.step, p.steps[index])
            wait(lambda: np.allclose(json.loads(js('JSON.stringify(calculationApp.view.model.atoms.map(a=>[a.x,a.y,a.z]))')),
                                     w.calculation.coords[p.steps[index]], atol=1e-8))
        panel.table.selectRow(0)
        w.advance()
        assert w.step == p.steps[1] and panel.table.currentRow() == 1
        panel.units.setCurrentText('Eh')
        panel.reference.setCurrentIndex(2)
        np.testing.assert_allclose(panel.values(), p.energies)
        with tempfile.TemporaryDirectory() as directory:
            csvpath = Path(directory)/'path.csv'
            panel.export(csvpath)
            rows = list(csv.DictReader(csvpath.open()))
            assert len(rows) == len(p.energies)
            assert int(rows[1]['geometry_1_based']) == p.steps[1]+1
            panel.figure.savefig(Path(directory)/'path.svg')
            assert (Path(directory)/'path.svg').stat().st_size > 1000
        panel.units.setCurrentText('kcal/mol')
        panel.reference.setCurrentIndex(0)
        if p.parameters.shape[1] == 2:
            assert panel.colorbar is not None
            app.processEvents()
            w.grab().save(str(Path(tempfile.gettempdir())/'molecule-studio-scan2d.png'))
        print('PASS path import, selection, playback, units and export: '+name, flush=True)
    w.open_paths([Path(__file__).parent/'data'/'gaussian-eom-opt.log'])
    wait(lambda: not w.busy)
    assert len(w.calculation.coords) == 5
    assert panel.table.rowCount() == 0 and not panel.export_button.isEnabled()
    assert w.results.currentIndex() == w.uv_tab
    print('PASS full excited-state optimization and previous-path clearing', flush=True)
finally:
    w.close()
    app.processEvents()
