"""Actual desktop picking: explicit measurements in Calculation, Figure, and Build."""
import json
from pathlib import Path
import sys
import tempfile
import time

from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
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
w.builder_bridge.error.connect(errors.append)
QMessageBox.warning = lambda parent, title, message: errors.append(message)


def pump(seconds=.1):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(.005)


def wait(check, timeout=45):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        assert not errors, errors
        if check():
            return
        pump(.02)
    raise AssertionError('Timed out: ' + w.statusBar().currentMessage())


def js(code):
    result = []
    (w.builder_web if w.builder_active else w.web).page().runJavaScript('JSON.stringify(' + code + ')', result.append)
    wait(lambda: result)
    return json.loads(result[0]) if result[0] else None


def view(code):
    return js(('builderApp' if w.builder_active else 'calculationApp') + '.view.' + code)


def orient():
    name = 'builderApp' if w.builder_active else 'calculationApp'
    js(f'(()=>{{const v={name}.view;v.camera.position.set(8,7,10);v.camera.lookAt(v.controls.target);v.controls.update();v.invalidate();return true;}})()')
    pump()


def atom_point(index):
    name = 'builderApp' if w.builder_active else 'calculationApp'
    point = js(f'''(()=>{{const v={name}.view,a=v.model.atoms[{index}],r=v.renderer.domElement.getBoundingClientRect();
        const p=v.camera.position.clone().set(a.x,a.y,a.z).project(v.camera);
        return [r.left+(p.x+1)*r.width/2,r.top+(1-p.y)*r.height/2];}})()''')
    assert view(f'pick({{clientX:{point[0]},clientY:{point[1]}}})') == index, (index, point)
    return QPoint(round(point[0]), round(point[1]))


def click(*indices):
    widget = w.builder_web if w.builder_active else w.web
    for index in indices:
        QTest.mouseClick(widget.focusProxy() or widget, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, atom_point(index))
        pump()


def mode(count):
    if not w.measure_button.isChecked():
        w.measure_button.click()
        wait(lambda: w.measure_button.isChecked())
    w.measurement_kind.setCurrentIndex(w.measurement_kind.findData(count))
    wait(lambda: view('measurementCount') == count and w.measurement_panel.isVisible())
    pump()


def clear():
    w.measurement_clear.click()
    wait(lambda: view('selection') == [])


try:
    wait(lambda: w.renderer_ready and w.builder_ready)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        frame = '4\nMeasurement geometry\nC -2 0 0\nC 0 0 0\nO 0 2 0\nH 0 2 2\n'
        second = frame.replace('C -2 0 0', 'C -3 0 0')
        trajectory = root / 'measurements.xyz'
        trajectory.write_text(frame + second)
        w.open_paths([trajectory])
        wait(lambda: w.calculation is not None and not w.busy)
        w.slider.setValue(0)
        wait(lambda: view('model.atoms.length') == 4 and view('model.atoms[0].x') == -2)
        mode(2)
        orient()
        original = view('model')
        click(0, 1)
        wait(lambda: '2.00 Å' in w.measurement_readout.text())
        assert 'C1 → C2' in w.measurement_readout.text()
        assert view('measureLine.visible')
        assert view('model') == original
        w.slider.setValue(1)
        wait(lambda: '3.00 Å' in w.measurement_readout.text())
        assert view('selection') == [0, 1]
        click(2)
        assert view('selection') == [2] and not view('measureLine.visible')
        clear()
        mode(3)
        click(0, 1)
        assert '2/3' in w.measurement_readout.text() and not view('measureLine.visible')
        click(2)
        wait(lambda: '90.0 °' in w.measurement_readout.text())
        assert 'Angle' in w.measurement_readout.text()
        mode(4)
        click(0, 1, 2, 3)
        wait(lambda: '90.0 °' in w.measurement_readout.text())
        assert 'Dihedral' in w.measurement_readout.text()
        assert view('selection') == [0, 1, 2, 3]
        w.builder_hydrogens.setChecked(False)
        wait(lambda: not view('measureLine.visible'))
        assert '3/4' in w.measurement_readout.text()
        w.builder_hydrogens.setChecked(True)
        wait(lambda: view('measureLine.visible'))
        widget = w.web.focusProxy() or w.web
        QTest.keyClick(widget, Qt.Key.Key_Escape)
        wait(lambda: not view('selection'))
        assert not view('measureLabel.visible')
        mode(2)
        click(0, 1)
        baseline = w.measurement_readout.text()
        w.send(type='vibration', xyz=second, vectors=[[1, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]],
               mode=0, amplitude=.3, playing=True)
        wait(lambda: w.measurement_readout.text() != baseline)
        assert view('selection') == [0, 1]
        w.send(type='vibrationStop')
        wait(lambda: '3.00 Å' in w.measurement_readout.text())
        pump(.3)
        idle = view('frameCount')
        pump(.3)
        assert view('frameCount') == idle
        print('PASS: distances, angles, dihedrals, ordered picks, hidden H, Escape, trajectory/vibration updates, zero idle draws.', flush=True)

        w.copy_selected_geometry()
        wait(lambda: w.builder_active and view('model.atoms.length') == 4)
        w.choose_builder_tool('delete')
        wait(lambda: js('builderApp.editor.tool') == 'delete')
        mode(2)
        wait(lambda: js('builderApp.editor.tool') == 'select')
        orient()
        before = view('model')
        undo = js('builderApp.editor.undoStack.length')
        click(0, 1)
        wait(lambda: '3.00 Å' in w.measurement_readout.text())
        assert view('model') == before and js('builderApp.editor.undoStack.length') == undo
        # Moving the two measured atoms together preserves length and moves the guide live.
        w.choose_builder_tool('move')
        wait(lambda: js('builderApp.editor.tool') == 'move')
        widget = w.builder_web.focusProxy() or w.builder_web
        start = atom_point(0)
        old_line = view('measureLine.geometry.attributes.position.array[0]')
        QTest.mousePress(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(widget, start + QPoint(24, 12), 80)
        pump()
        assert view('measureLine.geometry.attributes.position.array[0]') != old_line
        assert '3.00 Å' in w.measurement_readout.text()
        QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start + QPoint(24, 12))
        pump()
        w.builder_command(type='undo')
        wait(lambda: view('model') == before)
        w.preview_builder_figure()
        wait(lambda: js('builderApp.editor.locked'))
        clear()
        mode(4)
        click(0, 1, 2, 3)
        wait(lambda: 'Dihedral' in w.measurement_readout.text() and '90.0 °' in w.measurement_readout.text())
        assert view('model') == before
        QTest.keyClick(w.builder_web.focusProxy() or w.builder_web, Qt.Key.Key_Escape)
        wait(lambda: not view('selection'))
        w.measure_button.click()
        wait(lambda: view('measurementCount') == 0 and not w.measurement_panel.isVisible())
        print('PASS: measuring leaves geometry/history unchanged, takes over from Delete, updates during real drags, and works in read-only Figure.', flush=True)

        w.inspector.setCurrentIndex(0)
        wait(lambda: not w.builder_active)
        mode(2)
        orient()
        clear()
        click(0, 1)
        another = root / 'another.xyz'
        another.write_text(second)
        previous = w.calculation
        w.open_paths([another])
        wait(lambda: not w.busy and w.calculation is not previous)
        wait(lambda: not view('selection'))
        assert '0/2' in w.measurement_readout.text()
        w.inspector.setCurrentIndex(w.compare_tab)
        wait(lambda: view('model.atoms.length') == 8)
        assert w.measure_button.isVisible()
        # Compare uses the same controls and math even with overlaid coincident atoms.
        js('calculationApp.view.updateOverlays([0,1],null)')
        wait(lambda: '3.00 Å' in w.measurement_readout.text())
        print('PASS: new documents clear picks; Compare uses the shared measurement tool.', flush=True)
    assert not errors, errors
finally:
    w.close()
    pump(.2)
