"""Real offline GPU export, bond annotation, animation and cancellation checks."""
import base64
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import time

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from molecule_studio.app import Window, configure_app
from molecule_studio.data import Calculation

app = QApplication([])
configure_app(app)
errors = []
QMessageBox.warning = lambda *args: errors.append(str(args[1:]))
w = Window()
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
w.show()
w.bridge.error.connect(errors.append)
w.builder_bridge.error.connect(errors.append)


def pump(seconds=.05):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(.005)


def wait(check, timeout=180):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        if errors:
            raise AssertionError(errors)
        if check():
            return
        pump()
    raise AssertionError('Timeout: '+w.statusBar().currentMessage())


def js(code, builder=False):
    result = []
    (w.builder_web if builder else w.web).page().runJavaScript(code, result.append)
    wait(lambda: result)
    return result[0]


def snapshot():
    return js('JSON.stringify({model:calculationApp.view.model,camera:calculationApp.view.cameraState()})')


def decoded_movie(path, expected_frames, width):
    # Decode the actual WebM using the same Chromium runtime, with no test codec dependency.
    js("""window.movieCheck={};window.testMovie=document.createElement('video');
        testMovie.preload='auto';testMovie.onloadeddata=()=>{movieCheck.width=testMovie.videoWidth;movieCheck.duration=testMovie.duration;};
        testMovie.onerror=()=>{movieCheck.error=testMovie.error.message;};
        testMovie.src=""" + json.dumps(path.as_uri()))
    wait(lambda: js('!!movieCheck.width||!!movieCheck.error'))
    info = js('JSON.stringify(movieCheck)')
    info = json.loads(info)
    assert 'error' not in info, info
    assert info['width'] == width, info
    assert abs(info['duration']-expected_frames/w.video_fps.value()) < .003, info
    js("""window.moviePixels=[];
        window.movieSample=()=>{const c=document.createElement('canvas');c.width=testMovie.videoWidth;c.height=testMovie.videoHeight;
        c.getContext('2d').drawImage(testMovie,0,0);moviePixels.push(c.toDataURL());};movieSample();""")
    js('testMovie.onseeked=movieSample;testMovie.currentTime='+str((expected_frames//4+.5)/w.video_fps.value()))
    wait(lambda: js('moviePixels.length') >= 2)
    assert js('moviePixels[0]!==moviePixels[1]'), 'Decoded movie frames did not move'
    js("testMovie.removeAttribute('src');testMovie.load();testMovie.remove();")


try:
    wait(lambda: w.renderer_ready and w.builder_ready)
    base = np.array([[0., 0, 0], [2.5, 0, 0], [0, 2.5, 0]])
    calc = Calculation('Renderer check', np.array([7, 30, 8]),
                       np.array([base, base+[0, .4, 0], base+[0, .8, 0], base+[0, 1.2, 0]]),
                       np.array([-1., -.9, -.8, -.7]))
    w.loaded(('calculation', calc, None))
    wait(lambda: js('calculationApp.view.model.atoms.length') == 3)
    js('calculationApp.view.updateOverlays([0,1],null)')
    w.send(type='annotation', kind='dative')
    pump()
    js('calculationApp.view.updateOverlays([0,2],null)')
    w.send(type='annotation', kind='ts')
    pump()
    assert js('calculationApp.view.arrowMesh.count') == 1
    assert js('calculationApp.view.halves.length') == 10
    w.select_step(0)
    pump()
    assert json.loads(js('JSON.stringify(calculationApp.view.model.bonds)')) == [
        dict(a=0, b=1, order=1, kind='dative'), dict(a=0, b=2, order=1, kind='ts')]
    before = snapshot()
    w.export_engine.setCurrentIndex(1)
    w.export_size.setMinimum(64)
    w.export_size.setValue(192)
    w.ray_samples.setValue(4)
    w.transparent.setChecked(True)
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        image_path = directory/'ray.png'
        w.render_export(image_path)
        wait(lambda: image_path.exists() and not w.exporting)
        with Image.open(image_path) as image:
            assert max(image.size) == 192
            assert image.getchannel('A').getextrema() == (0, 255)
            assert image.getpixel((0, 0))[3] == 0
        assert snapshot() == before
        print('PASS: shared dative arrows, TS dashes, trajectory persistence, actual ray tracing and transparent PNG.', flush=True)
        w.video_size.addItem('96 px', 96)
        w.video_size.setCurrentIndex(w.video_size.count()-1)
        w.video_hold.setValue(1)
        w.ray_samples.setValue(2)
        path = directory/'trajectory.webm'
        w.render_video(path)
        wait(lambda: path.exists() and not w.exporting)
        assert path.read_bytes()[:4] == b'\x1aE\xdf\xa3'
        assert snapshot() == before
        decoded_movie(path, 4, 96)
        print('PASS: complete trajectory encoded offline and decoded at the requested size, timing and motion.', flush=True)

        # A real reported normal mode, not a synthetic displacement fixture.
        w.open_paths([Path(__file__).parent/'data/gaussian-freq.log'])
        wait(lambda: w.calculation is not calc and not w.busy)
        w.results.setCurrentIndex(w.vibration_tab)
        mode = int(np.argmin(w.calculation.frequencies))
        # The vectors are reported data; change only the sign to exercise imaginary-mode UI/export.
        frequencies = w.calculation.frequencies.copy()
        frequencies[mode] = -abs(frequencies[mode])
        w.calculation = replace(w.calculation, frequencies=frequencies)
        w.refresh_results()
        w.vibration_table.selectRow(mode)
        pump()
        assert 'Imaginary' in w.vibration_note.text()
        js('calculationApp.view.updateOverlays([0,1],null)')
        w.send(type='annotation', kind='ts')
        pump()
        before = snapshot()
        w.video_source.setCurrentIndex(2)
        w.video_period.setValue(8)
        w.video_cycles.setValue(1)
        path = directory/'mode.webm'
        w.render_video(path)
        wait(lambda: path.exists() and not w.exporting)
        assert snapshot() == before
        decoded_movie(path, 8, 96)
        print('PASS: selected reported vibrational mode, TS contact, decoded animation and exact state restoration.', flush=True)

        path = directory/'cancelled.webm'
        path.write_bytes(b'previous file')
        w.ray_samples.setValue(1024)
        w.render_video(path)
        QTimer.singleShot(150, lambda: w.send(type='exportCancel'))
        wait(lambda: not w.exporting)
        assert path.read_bytes() == b'previous file'
        assert not list(directory.glob('.molecule-studio-*'))
        assert snapshot() == before
        pump(.3)
        count = js('calculationApp.view.frameCount')
        pump(.4)
        assert js('calculationApp.view.frameCount') == count
        print('PASS: cancellation preserves existing files, removes temporary output, restores the scene and returns to zero idle frames.', flush=True)
        # Invisible instances must not consume the ray-tracing triangle budget.
        model = dict(name='Hidden hydrogens', atoms=[dict(el='C', x=0, y=0, z=0)]+
                     [dict(el='H', x=0, y=0, z=0) for _ in range(1000)], bonds=[])
        w.inspector.setCurrentIndex(w.build_tab)
        w.builder_command(type='restore', model=model)
        wait(lambda: w.builder_state.get('atoms') == 1001)
        w.builder_hydrogens.setChecked(False)
        w.ray_samples.setValue(2)
        path = directory/'hidden.png'
        w.render_export(path)
        wait(lambda: path.exists() and not w.exporting)
        with Image.open(path) as image:
            assert image.getchannel('A').getextrema() == (0, 255)
        print('PASS: hidden atoms are excluded from ray-tracing geometry and budget; Build exports use the same engine.', flush=True)
finally:
    w.close()
    app.processEvents()
