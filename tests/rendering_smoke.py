"""Shared appearance, stationary camera, and demand-rendering regression checks."""
import json
from pathlib import Path
import sys
import tempfile
import time
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from molecule_studio.app import Window,configure_app
app=QApplication([]);configure_app(app)
w=Window();w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);w.show()
errors=[];w.bridge.error.connect(errors.append);w.builder_bridge.error.connect(errors.append)
def pump(seconds=.3):
    until=time.monotonic()+seconds
    while time.monotonic()<until:app.processEvents();time.sleep(.01)
def wait(fn,timeout=25):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if errors:raise AssertionError(errors)
        if fn():return
        pump(.02)
    raise AssertionError('Timed out')
def js(code,builder=False):
    result=[];(w.builder_web if builder else w.web).page().runJavaScript(code,lambda x:result.append(x));wait(lambda:result);return result[0]
def view(code,builder=False):return js(('builderApp' if builder else 'calculationApp')+'.view.'+code,builder)
def idle(builder):
    pump(.4);before=view('frameCount',builder);camera=view('cameraState()',builder);pump(.6)
    assert view('frameCount',builder)==before,(builder,before,view('frameCount',builder))
    assert view('cameraState()',builder)==camera
    assert view('controls.staticMoving',builder) is True
    return before
try:
    wait(lambda:w.renderer_ready and w.builder_ready)
    w.open_paths([Path(__file__).parent/'data/gaussian-opt.log']);wait(lambda:w.calculation and not w.busy)
    w.inspector.setCurrentIndex(3);w.copy_selected_geometry();wait(lambda:w.builder_state.get('atoms')==20)
    for preset in ['Studio','Paton-inspired','Soft studio']:
        w.preset.setCurrentText(preset);pump()
        for rep in ['Ball and stick','Stick','Space filling']:
            w.style.setCurrentText(rep);pump(.1)
            assert view('style')==view('style',True)
            assert view('appearance')==view('appearance',True)
            for property in ["radius({el:'C'})","bondRadius()","color({el:'O'})","camera.isOrthographicCamera"]:
                assert view(property)==view(property,True),(preset,rep,property)
    w.builder_hydrogens.setChecked(False);w.builder_labels.setChecked(True);w.builder_size.setValue(120)
    w.view_background.setCurrentIndex(1);pump()
    assert view('style')==view('style',True)
    assert view('labels.children.length')==view('labels.children.length',True)
    assert view('visible(0)')==view('visible(0)',True)
    w.preset.setCurrentText('Studio');w.style.setCurrentText('Ball and stick');pump()
    idle(True);idle(False)
    # Real orbit gesture must stop immediately, with no momentum tail.
    target=w.builder_web.focusProxy() or w.builder_web
    x,y=w.builder_web.width()//2,w.builder_web.height()//2
    QTest.mousePress(target,Qt.MouseButton.MiddleButton,Qt.KeyboardModifier.NoModifier,QPoint(x,y))
    QTest.mouseMove(target,QPoint(x+80,y+35),30)
    QTest.mouseRelease(target,Qt.MouseButton.MiddleButton,Qt.KeyboardModifier.NoModifier,QPoint(x+80,y+35))
    idle(True)
    camera=view('cameraState()',True)
    w.preview_builder_figure();pump()
    assert w.viewer_stack.currentWidget()==w.builder_web
    assert camera==view('cameraState()',True)
    assert view('overlays.visible',True) is True  # Figure mode permits atom selection for bond styling.
    # Spin runs only in the visible view and stops drawing when turned off.
    w.builder_spin.setChecked(True);pump(.3)
    before=view('frameCount',True);hidden=view('frameCount');pump(.5)
    assert view('frameCount',True)>before
    assert view('frameCount')==hidden
    w.builder_spin.setChecked(False);idle(True)
    w.inspector.setCurrentIndex(0);pump();idle(False);idle(True)
    w.builder_spin.setChecked(True);pump(.2)
    before=view('frameCount');hidden=view('frameCount',True);pump(.4)
    assert view('frameCount')>before and view('frameCount',True)==hidden
    w.builder_spin.setChecked(False);idle(False)
    with tempfile.TemporaryDirectory() as d:
        for preset in ['Studio','Soft studio']:
            w.preset.setCurrentText(preset);w.transparent.setChecked(True);w.export_size.setValue(800)
            path=Path(d)/f'{preset}.png';w.render_export(path);wait(lambda:path.exists(),60)
            image=Image.open(path).convert('RGBA')
            if image.getpixel((0,0))[3]!=0:
                image.save('/tmp/studio-alpha-failure.png')
                print(js("JSON.stringify({camera:calculationApp.view.cameraState(),alpha:calculationApp.view.renderer.getClearAlpha(),background:calculationApp.view.scene.background?.getHexString()})"),flush=True)
            assert image.getpixel((0,0))[3]==0,(preset,image.getpixel((0,0)))
            assert image.getchannel('A').getextrema()[1]>0,preset
            idle(False)
    print('PASS: identical 3D styles/options, camera preserved in Figure, no momentum, zero idle frames in both views, hidden spin suspended, alpha exports including AO.',flush=True)
finally:w.close();app.processEvents()
