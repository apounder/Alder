"""Real desktop gestures and exports: persistent figure bonds, depth cue, and XYZ."""
import json
from pathlib import Path
import sys
import tempfile
import time

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QPoint, QPointF, QMimeData, QUrl, QEvent
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from molecule_studio.app import Window, configure_app

app = QApplication([])
configure_app(app)
w = Window()
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
w.show()
errors = []
commands = []
for bridge in (w.bridge, w.builder_bridge):
    bridge.command.connect(lambda value: commands.append(json.loads(value)))
w.bridge.error.connect(errors.append)
w.builder_bridge.error.connect(errors.append)
QMessageBox.warning = lambda parent, title, message: errors.append(message)


def pump(seconds=.1):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(.005)


def wait(check, timeout=45):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        if errors:
            raise AssertionError(errors)
        if check():
            return
        pump(.02)
    raise AssertionError('Timed out: '+w.statusBar().currentMessage())


def js(code, builder=False):
    result = []
    (w.builder_web if builder else w.web).page().runJavaScript('JSON.stringify('+code+')', result.append)
    wait(lambda: result)
    return json.loads(result[0]) if result[0] else None


def view(code, builder=False):
    return js(('builderApp' if builder else 'calculationApp')+'.view.'+code, builder)


def bonds(builder=False):
    return view('model.bonds', builder)


def click_atom(index, builder=False):
    name = 'builderApp' if builder else 'calculationApp'
    point = js(f'''(()=>{{const v={name}.view,a=v.model.atoms[{index}],r=v.renderer.domElement.getBoundingClientRect();
        const p=v.camera.position.clone().set(a.x,a.y,a.z).project(v.camera);
        return [r.left+(p.x+1)*r.width/2,r.top+(1-p.y)*r.height/2];}})()''', builder)
    assert view(f'pick({{clientX:{point[0]},clientY:{point[1]}}})', builder) == index
    widget = w.builder_web if builder else w.web
    QTest.mouseClick(widget.focusProxy() or widget, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(round(point[0]), round(point[1])))
    pump()


def annotate(a, b, kind):
    js(f'calculationApp.view.updateOverlays([{a},{b}],null)')
    w.send(type='annotation', kind=kind)
    pump()


try:
    wait(lambda: w.renderer_ready and w.builder_ready)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        frame = '4\nSaved geometry\nN -2.4 0 0\nC 0 0 0\nO 2.4 0 -1\nH 0 1.09 0\n'
        single = root/'single.xyz'
        single.write_text(frame)
        w.open_paths([single])
        wait(lambda: w.calculation is not None and not w.busy)
        wait(lambda: view('model.atoms.length') == 4)
        assert not w.builder_active and len(w.calculation.coords) == 1
        assert np.isnan(w.calculation.energies).all()
        annotate(0, 1, 'dative')
        annotate(1, 2, 'ts')
        annotate(0, 3, 'triple')
        annotate(1, 3, 'remove')
        expected = bonds()
        assert len(expected) == 3 and expected[2]['order'] == 3, expected
        calc = w.calculation
        original = calc.coords.copy()
        multi = root/'trajectory.xyz'
        multi.write_text(frame+frame.replace('H 0 1.09 0', 'H 0 1.12 0'))
        # Exercise the same native drop handler used by the embedded canvas.
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(multi))])
        drop = QDropEvent(QPointF(20, 20), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        assert drop.type() == QEvent.Type.Drop and w.eventFilter(w.web, drop)
        wait(lambda: not w.busy and w.calculation is not calc)
        assert len(w.calculation.coords) == 2 and w.slider.maximum() == 1
        annotate(0, 1, 'ts')
        trajectory_bonds = bonds()
        w.slider.setValue(0)
        w.slider.setValue(1)
        wait(lambda: abs(view('model.atoms[3].y')-1.12) < 1e-8)
        assert bonds() == trajectory_bonds
        w.calculation_picker.setCurrentIndex(0)
        wait(lambda: bonds() == expected)
        w.inspector.setCurrentIndex(w.compare_tab)
        wait(lambda: view('model.atoms.length') == 8)
        assert bonds()[:3] == expected
        assert all(b['a'] >= 4 and b['b'] >= 4 for b in bonds()[3:])
        w.inspector.setCurrentIndex(2)
        assert bonds()[:3] == expected
        w.inspector.setCurrentIndex(0)
        wait(lambda: bonds() == expected)
        w.copy_selected_geometry()
        wait(lambda: w.builder_active and bonds(True) == expected)
        np.testing.assert_array_equal(calc.coords, original)
        w.preview_builder_figure()
        pump()
        print('PASS: single/multi-frame XYZ, original coordinates and bonds across comparison, copy, Figure edits and MOL round trip.', flush=True)
        assert js('builderApp.editor.locked', True)
        click_atom(0, True)
        click_atom(1, True)
        assert js('builderApp.editor.selection', True) == [0, 1]
        for kind in ['remove', 'single', 'double', 'ts', 'dative']:
            w.send(type='annotation', kind=kind)
            pump()
            pair = [b for b in bonds(True) if {b['a'], b['b']} == {0, 1}]
            assert (not pair) if kind == 'remove' else len(pair) == 1
            if kind in ['ts', 'dative']:
                assert pair[0]['kind'] == kind
            elif kind != 'remove':
                assert pair[0]['order'] == (2 if kind == 'double' else 1)
            assert js('builderApp.editor.locked', True)
        saved = bonds(True)
        assert view('model.atoms.length', True) == 4  # Figure edits do not adjust hydrogens.
        mol = root/'edited.mol'
        w.export_builder('mol', mol)
        wait(mol.exists)
        w.open_paths([mol])
        wait(lambda: not w.busy and bonds(True) == saved)
        w.preview_builder_figure()
        pump()

        # Atom picking sets fog without mutating the molecule or selecting an atom.
        before = view('model', True)
        selection = js('builderApp.editor.selection', True)
        w.depth_cue.click()
        pump()
        assert view('depthPicking', True) and w.fog_enabled.isChecked()
        click_atom(2, True)
        assert not w.depth_cue.isChecked() and not view('depthPicking', True)
        assert js('builderApp.editor.selection', True) == selection and view('model', True) == before
        assert view('fogOptions') == view('fogOptions', True)
        camera = view('cameraState()', True)
        depth = w.fog_depth.value()
        target = w.builder_web.focusProxy() or w.builder_web
        assert view('pick({clientX:20,clientY:20})', True) is None
        QTest.mousePress(target, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, QPoint(20, 20))
        QTest.mouseMove(target, QPoint(120, 20), 50)
        QTest.mouseRelease(target, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, QPoint(120, 20))
        pump()
        assert w.fog_depth.value() > depth and camera == view('cameraState()', True)
        assert view('controls.enabled', True)
        w.depth_cue.click()
        pump()
        QTest.keyClick(target, Qt.Key.Key_Escape)
        pump()
        assert not w.depth_cue.isChecked() and not view('depthPicking', True)
        print('PASS: depth-cue atom picking, shared fog, right-drag adjustment without camera movement.', flush=True)
        w.fog_enabled.setChecked(False)
        pump()
        assert view('scene.fog', True) is None and view('scene.fog') is None
        w.fog_enabled.setChecked(True)
        w.fog_strength.setValue(100)
        w.fog_depth.setValue(-100)
        w.builder_labels.setChecked(True)
        w.transparent.setChecked(True)
        w.export_size.setMinimum(64)
        w.export_size.setValue(192)
        for engine in [0, 1]:
            w.export_engine.setCurrentIndex(engine)
            w.ray_samples.setValue(2)
            path = root/f'fog-{engine}.png'
            print(f'Exporting fog image with engine {engine}', flush=True)
            w.render_export(path)
            wait(lambda: not w.exporting, 240)
            assert path.exists(), (w.statusBar().currentMessage(), [c for c in commands if c['type'] in ['export','figure','exportCancel']])
            pixels = np.asarray(Image.open(path).convert('RGBA'))
            assert pixels[0, 0, 3] == 0 and pixels[:, :, 3].max() == 255
            opaque = pixels[:, :, 3] == 255
            # At two samples, ray-traced silhouettes can differ slightly from
            # the antialiased depth pass. Check interior pixels, not coverage edges.
            interior=opaque.copy()
            for dy,dx in [(0,1),(0,-1),(1,0),(-1,0),(1,1),(-1,-1),(-1,1),(1,-1)]:
                interior &= np.roll(opaque,(dy,dx),(0,1))
            assert interior.any()
            assert (pixels[:, :, :3][interior] >= 250).all(), (engine, pixels[:, :, :3][interior].min(axis=0))
            assert bonds(True) == saved and view('model', True) == before
        pump(.4)
        count = view('frameCount', True)
        pump(.4)
        assert view('frameCount', True) == count, 'Fog must not create an idle render loop'
    print('PASS: XYZ open/drop/frames, edited bonds across views/copies/MOL, Figure selection, fog pick/right-drag/toggle, transparent Studio/ray figures and zero idle rendering.', flush=True)
finally:
    w.close()
    app.processEvents()
