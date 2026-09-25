"""Run explicitly on a desktop: python tests/gui_smoke.py [screenshot.png]."""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from alder.app import Window, configure_app
from alder.data import BOHR


def wait_for(condition, timeout=25):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        app.processEvents()
        if errors:
            raise AssertionError(errors)
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for desktop state; errors=" + str(errors))


def javascript(code):
    result = []
    window.web.page().runJavaScript(code, lambda value: result.append(value))
    wait_for(lambda: result)
    return result[0]


def state():
    return json.loads(javascript("JSON.stringify(window.sceneState)"))


def drop(path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path.resolve()))])
    target = window.web.focusProxy() or window.web
    QApplication.sendEvent(target, QDragEnterEvent(QPoint(100, 100), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    QApplication.sendEvent(target, QDropEvent(QPointF(100, 100), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    wait_for(lambda: not window.busy)
    assert not errors, errors


app = QApplication([])
configure_app(app)
window = Window()
window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
errors = []
window.bridge.error.connect(errors.append)
QMessageBox.warning = lambda parent, title, message: errors.append(message)
window.show()
try:
    wait_for(lambda: window.renderer_ready or errors)
    assert window.renderer_ready, errors
    assert window.trajectory_speed.value() == 10 and window.timer.interval() == 35
    viewer_height = window.web.height()
    window.results_toggle.click()
    app.processEvents()
    assert not window.results.isVisible() and window.web.height() > viewer_height
    window.results_toggle.click()
    app.processEvents()
    assert window.results.isVisible()
    data = Path(__file__).parent / "data"
    drop(data / "gaussian-opt.log")
    wait_for(lambda: state()["atoms"] == 20)
    assert window.step == 4
    assert javascript("calculationApp.view.atomMesh.geometry.parameters.widthSegments") == 48
    window.slider.setValue(0)
    assert window.step == 0
    assert "382.294279" in window.energy_label.text()
    window.trajectory_speed.setValue(40)
    assert window.timer.interval() == 16
    with patch("alder.app.time.monotonic", return_value=100.0):
        window.play.setChecked(True)
    with patch("alder.app.time.monotonic", return_value=100.036):
        window.advance()
    assert window.step == 4
    window.play.setChecked(False)
    window.trajectory_speed.setValue(10)
    window.slider.setValue(0)
    window.play.setChecked(True)
    wait_for(lambda: window.step != 0)
    window.play.setChecked(False)
    drop(data / "orca-opt.out")
    assert len(window.calculation.coords) == 4
    drop(data / "orca6-opt.out")
    assert window.calculation.summary["Program"] == "ORCA"
    drop(data / "gaussian-opt.log")

    # Synthetic p-like scalar field for renderer testing, not a computed orbital.
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        calc = window.calculation
        points = calc.coords[-1] / BOHR
        origin = points.min(axis=0) - 3
        counts = np.array([36, 30, 28])
        spacing = (points.max(axis=0) + 3 - origin) / (counts - 1)
        x, y, z = np.meshgrid(*(origin[i] + np.arange(counts[i]) * spacing[i] for i in range(3)), indexing="ij")
        field = (z - points[0, 2]) * np.exp(-((x-points[0, 0])**2 + (y-points[0, 1])**2 + (z-points[0, 2])**2) / 3)
        lines = ["Synthetic signed field - not a computed orbital", "GUI test", f"20 {' '.join(map(str, origin))}"]
        for i in range(3):
            axis = np.zeros(3); axis[i] = spacing[i]
            lines.append(f"{counts[i]} {' '.join(map(str, axis))}")
        for atom, point in zip(calc.atomnos, points):
            lines.append(f"{atom} 0 {' '.join(map(str, point))}")
        lines.append(" ".join(f"{value:.6e}" for value in field.flat))
        cube = temp / "synthetic-test.cube"
        cube.write_text("\n".join(lines))
        drop(cube)
        wait_for(lambda: state()["surfaces"] == 2)
        assert window.cube_step == 4
        assert not errors, errors
        window.slider.setValue(0)
        wait_for(lambda: state()["surfaces"] == 0)
        window.slider.setValue(4)
        wait_for(lambda: state()["surfaces"] == 2)
        window.isovalue.setValue(0.08)
        window.opacity.setValue(45)
        wait_for(lambda: not window.surface_timer.isActive())
        assert javascript("calculationApp.surfaceOptions.isoval") == 0.08
        png = temp / "surface.png"
        window.export_size.setValue(800)
        window.render_export(png)
        wait_for(lambda: png.exists())
        assert png.read_bytes().startswith(b"\x89PNG")
        assert png.stat().st_size > 5000
        # Verify that the embedded desktop view actually displays the pixels,
        # not just that Chromium can export an offscreen PNG.
        javascript("calculationApp.view.camera.position.x+=3; calculationApp.view.controls.update();")
        wait_for(lambda: window.web.isVisible())
        for _ in range(15):
            app.processEvents()
            time.sleep(0.03)
        view_png = temp / "embedded.png"
        window.web.grab().save(str(view_png))
        pixels = np.asarray(Image.open(view_png).convert("RGB"))
        interior = pixels[30:-40, 30:-30].astype(float)
        assert np.std(interior, axis=(0, 1)).mean() > 10, "Embedded 3D view is blank"
        if len(sys.argv) > 1:
            window.grab().save(sys.argv[1])
        window.clear_cube()
        wait_for(lambda: state()["surfaces"] == 0)
        assert not errors, errors

        # Paired fields with known values exercise actual vertex coloring, not
        # merely the presence of a surface object.
        header = lines[:-1]
        radius2 = (x-points[0, 0])**2 + (y-points[0, 1])**2 + (z-points[0, 2])**2
        density = 0.05*np.exp(-radius2 / 4)
        potential = 0.012*(z-points[0, 2])

        def field_file(name, values):
            path = temp / name
            path.write_text("\n".join(header) + "\n" + " ".join(f"{value:.7e}" for value in values.flat))
            return path

        density_path = field_file("density.cube", density)
        esp_path = field_file("esp.cube", potential)
        drop(density_path)
        drop(esp_path)
        assert window.surface_mode.currentData() == "esp"
        wait_for(lambda: state()["mapped"] and state()["surfaces"] == 1)
        values = javascript("JSON.stringify(Array.from(calculationApp.shapes[0].children[0].geometry.attributes.color.array).slice(0,900))")
        colors = np.asarray(json.loads(values)).reshape(-1, 3)
        assert np.ptp(colors, axis=0).max() > 0.2
        assert javascript("document.getElementById('colorScale').hidden") is False

        # Linear scalar fields must interpolate correctly between voxel nodes.
        probe = points[0].copy(); probe[2] += 0.83
        expected = 0.012 * 0.83
        args = ','.join(str(value * BOHR) for value in probe)
        observed = javascript(f"calculationApp.sampledField(calculationApp.colorVolume, 1).getVal({args})")
        assert abs(observed - expected) < 1e-6

        for mode, iso in [('nci', 0.02), ('igm', 0.01)]:
            window.surface_mode.setCurrentIndex(window.surface_mode.findData(mode))
            window.isovalue.setValue(iso)
            wait_for(lambda: not window.surface_timer.isActive())
            wait_for(lambda: javascript('calculationApp.surfaceOptions.mode') == mode)
            assert window.gradient.currentData() == 'nci'
            assert javascript('calculationApp.gradient(calculationApp.surfaceOptions).valueToHex(0)') == 0x52c85d

        scaled = field_file('nciplot-dens.cube', potential*100)
        drop(scaled)
        window.color_scale.setCurrentIndex(1)
        wait_for(lambda: not window.surface_timer.isActive())
        wait_for(lambda: javascript('calculationApp.surfaceOptions.scale') == 0.01)
        observed = javascript(f"calculationApp.sampledField(calculationApp.colorVolume, calculationApp.surfaceOptions.scale).getVal({args})")
        assert abs(observed - expected) < 1e-6

        # Mismatched grids are rejected, then a valid selection recovers.
        bad = temp / 'different-grid.cube'
        bad_lines = header.copy()
        bad_lines[2] = f"20 {' '.join(map(str, origin + [0.1, 0, 0]))}"
        bad.write_text('\n'.join(bad_lines) + '\n' + ' '.join(map(str, potential.flat)))
        drop(bad)
        assert 'different grids' in window.surface_message.text()
        wait_for(lambda: state()['surfaces'] == 0)
        window.color_field.setCurrentIndex(2)
        window.color_scale.setCurrentIndex(0)
        wait_for(lambda: state()['mapped'] and state()['surfaces'] == 1)

        # The Paton preset and export operate on the same camera/scene.
        window.surface_mode.setCurrentIndex(window.surface_mode.findData('esp'))
        window.preset.setCurrentText('Paton-inspired')
        wait_for(lambda: javascript('calculationApp.view.appearance.preset') == 'Paton-inspired')
        assert javascript("calculationApp.view.bondRadius()") == 0.07
        window.export_size.setValue(1600)
        window.export_samples.setCurrentIndex(0)
        window.transparent.setChecked(True)
        window.inspector.setCurrentIndex(2)
        output = temp / 'publication.png'
        before_camera = json.loads(javascript('JSON.stringify(calculationApp.view.cameraState())'))
        window.render_export(output)
        wait_for(lambda: output.exists(), timeout=60)
        rendered = Image.open(output)
        assert max(rendered.size) == 1600
        assert abs(max(state()['exportRenderSize']) - 3200) <= 2, state()
        assert before_camera == json.loads(javascript('JSON.stringify(calculationApp.view.cameraState())'))
        assert abs(rendered.info['dpi'][0] - 300) < 1
        assert rendered.convert('RGBA').getpixel((0, 0))[3] == 0
        alpha = np.asarray(rendered.convert('RGBA'))[:, :, 3]
        assert (alpha > 0).sum() > 10000, 'Export is empty'
        if len(sys.argv) > 1:
            rendered.save(str(Path(sys.argv[1]).with_name('figure-example.png')))
            window.grab().save(sys.argv[1])
        output_tiff = temp / 'publication.tiff'
        window.export_size.setValue(800)
        window.render_export(output_tiff)
        wait_for(lambda: output_tiff.exists(), timeout=60)
        assert max(Image.open(output_tiff).size) == 800
        assert Image.open(output_tiff).format == 'TIFF'

        window.surface_field.setCurrentIndex(2)  # ESP alone, on van der Waals radii.
        window.surface_mode.setCurrentIndex(window.surface_mode.findData('esp_vdw'))
        wait_for(lambda: javascript('calculationApp.surfaceOptions.mode') == 'esp_vdw' and state()['surfaces'] == 1)
        assert javascript('calculationApp.vdwSurface !== null') is True
        window.clear_cube()
        wait_for(lambda: state()['surfaces'] == 0)
    assert javascript("(()=>{const view=calculationApp.view;view.syncModel({atoms:Array.from({length:300},(_,i)=>({el:'C',x:(i%20)*3,y:Math.floor(i/20)*3,z:0})),bonds:[]});return view.atomMesh.geometry.parameters.widthSegments})()") == 24
    print("PASS: Gaussian/ORCA, file drop, playback, ESP/NCI/IGM colors, interpolation, NCIPLOT scaling, grid rejection/recovery, Paton style, supersampled transparent PNG/TIFF, and VDW ESP.", flush=True)
finally:
    window.close()
    app.processEvents()
