"""Offline Qt checks for the Rowan-style 2D/3D builder."""
import json
from pathlib import Path
import sys
import tempfile
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from molecule_studio.app import Window, configure_app

app=QApplication([]);configure_app(app)
window=Window();window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);window.show()
errors=[]
window.bridge.error.connect(errors.append)
window.builder_bridge.error.connect(errors.append)
window.sketch_bridge.message.connect(lambda message,kind: errors.append(message) if kind=='error' else None)

def wait(check, timeout=30):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        app.processEvents()
        if errors: raise AssertionError(errors)
        if check():return
        time.sleep(.02)
    raise AssertionError(f'Timeout: {window.builder_state}, sketch={getattr(window,"sketch_state",{})}, {window.statusBar().currentMessage()}')

def js(code,sketch=True):
    result=[]
    (window.sketch_web if sketch else window.builder_web).page().runJavaScript(code,lambda value:result.append(value))
    wait(lambda:result)
    return result[0]

try:
    wait(lambda:window.builder_ready and window.renderer_ready)
    window.inspector.setCurrentIndex(window.build_tab)
    window.builder_smiles.setText('c1ccccc1');window.builder_generate.click()
    wait(lambda:window.builder_state.get('atoms')==12 and not window.builder_state.get('busy'))
    original=json.dumps(window.builder_model,sort_keys=True)
    assert window.body.indexOf(window.inspector)==1
    window.builder_modes['2d'].click()
    wait(lambda:window.sketch_ready and not window.converting and getattr(window,'sketch_state',{}).get('atoms')==6)
    assert window.viewer_stack.currentWidget()==window.sketch_web
    assert json.dumps(window.builder_model,sort_keys=True)==original
    assert not window.sketch_dirty
    print('PASS offline Ketcher startup and 3D -> 2D without changing 3D coordinates',flush=True)
    # Changes stay in the sketch until the explicit conversion action.
    js("ketcher.setMolecule('CCO')")
    wait(lambda:getattr(window,'sketch_state',{}).get('atoms')==3 and window.sketch_dirty)
    window.sketch_command(type='undo')
    wait(lambda:getattr(window,'sketch_state',{}).get('atoms')==6)
    window.sketch_command(type='redo')
    wait(lambda:getattr(window,'sketch_state',{}).get('atoms')==3)
    window.sketch_command(type='layout')
    assert js("typeof ketcher.layout")=="function"
    window.builder_modes['3d'].click()
    assert json.dumps(window.builder_model,sort_keys=True)==original
    window.builder_modes['2d'].click()
    assert window.sketch_dirty
    assert js('ketcher.editor.struct().atoms.size')==3
    window.builder_convert.click()
    wait(lambda:window.builder_mode=='3d' and window.builder_state.get('atoms')==9 and not window.converting)
    assert window.builder_state['formula']=='C₂H₆O'
    assert window.builder_model.get('embedding')=='ETKDG + MMFF94'
    assert not window.sketch_dirty
    print('PASS edited 2D -> stereochemistry-aware native 3D conversion',flush=True)
    print("checking undo",flush=True)
    window.builder_undo.click()
    wait(lambda:window.builder_state.get('atoms')==12)
    assert json.dumps(window.builder_model,sort_keys=True)==original
    print('checking regenerated layout',flush=True)
    window.builder_modes['2d'].click()
    wait(lambda:getattr(window,'sketch_state',{}).get('atoms')==6 and not window.converting)
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        for fmt in ('mol','png','svg'):
            target=root/f'drawing.{fmt}'
            print('exporting',fmt,flush=True)
            window.export_sketch(fmt,target)
            wait(lambda:target.exists())
            assert target.stat().st_size>100
            if fmt=='mol':assert 'V2000' in target.read_text()
            if fmt=='svg':assert '<svg' in target.read_text()
    print('PASS exact 3D undo, 2D MOL/PNG/SVG export',flush=True)
    if len(sys.argv)>1:
        # Ensure Ketcher has painted the SVG drawing before capturing the native layout.
        for _ in range(20):app.processEvents();time.sleep(.025)
        window.grab().save(sys.argv[1])
finally:
    window.close();app.processEvents()
