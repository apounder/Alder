"""Actual Qt integration checks for building inside Molecule Studio."""
import json
from pathlib import Path
import sys
import tempfile
import time

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from molecule_studio.app import Window, configure_app
from molecule_studio.data import BOHR

app = QApplication([])
configure_app(app)
window = Window()
window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
errors = []
window.bridge.error.connect(errors.append)
window.builder_bridge.error.connect(errors.append)
QMessageBox.warning = lambda parent, title, message: errors.append(str(message))
window.show()
QApplication.setActiveWindow(window)
workspace = tempfile.TemporaryDirectory()

def wait(check, timeout=40):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        app.processEvents()
        if errors: raise AssertionError(errors)
        if check(): return
        time.sleep(.01)
    raise AssertionError('Timed out: '+str(window.builder_state)+'\n'+window.statusBar().currentMessage())

def js(code, builder=True):
    result=[]
    (window.builder_web if builder else window.web).page().runJavaScript(code, lambda value: result.append(value))
    wait(lambda: result)
    return result[0]

def atoms(count):
    wait(lambda: window.builder_state.get('atoms')==count)

def click_atom(index):
    for _ in range(5): app.processEvents(); time.sleep(.025)
    encoded=js(f'''JSON.stringify((()=>{{const v=builderApp.view,a=builderApp.model.atoms[{index}],p=v.camera.position.clone();v.camera.updateMatrixWorld();p.set(a.x,a.y,a.z).project(v.camera);return [(p.x+1)*innerWidth/2,(1-p.y)*innerHeight/2]}})())''')
    x,y=json.loads(encoded)
    assert 0<x<window.builder_web.width() and 0<y<window.builder_web.height(), (index,x,y,window.builder_web.size())
    picked=js(f'builderApp.view.pick({{clientX:{x},clientY:{y}}})')
    assert picked==index, (index,picked,x,y)
    target=window.builder_web.focusProxy() or window.builder_web
    QTest.mouseClick(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(round(x),round(y)))
    app.processEvents()

def drag_atom(index, dx=100, dy=0):
    x,y=json.loads(js(f"JSON.stringify((()=>{{const v=builderApp.view,a=builderApp.model.atoms[{index}],p=v.camera.position.clone();p.set(a.x,a.y,a.z).project(v.camera);return [(p.x+1)*innerWidth/2,(1-p.y)*innerHeight/2]}})())"))
    target=window.builder_web.focusProxy() or window.builder_web
    start=QPoint(round(x),round(y));end=start+QPoint(dx,dy)
    QTest.mousePress(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
    QTest.mouseMove(target,end,40);app.processEvents()
    QTest.mouseRelease(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
    app.processEvents()

try:
    wait(lambda: window.renderer_ready and window.builder_ready)
    data=Path(__file__).parent/'data'
    window.open_paths([data/'gaussian-opt.log'])
    wait(lambda: not window.busy and window.calculation is not None)
    original=window.calculation.coords.copy();energies=window.calculation.energies.copy()
    window.slider.setValue(1)
    cube_path=Path(workspace.name)/'synthetic.cube'
    cube_rows=['Synthetic test field','Not a calculated orbital',f'{len(window.calculation.atomnos)} 0 0 0','2 1 0 0','2 0 1 0','2 0 0 1']
    cube_rows += [f'{int(z)} 0 {x:.9f} {y:.9f} {v:.9f}' for z,(x,y,v) in zip(window.calculation.atomnos,original[1]/BOHR)]
    cube_rows += ['-0.1 0.1 -0.1 0.1 -0.1 0.1 -0.1 0.1']
    cube_path.write_text('\n'.join(cube_rows)+'\n')
    window.open_paths([cube_path]);wait(lambda:not window.busy and window.cube is not None)
    wait(lambda: js('sceneState.surfaces',False)==2)
    original_cube=window.cube
    window.inspector.setCurrentIndex(window.build_tab)
    window.builder_copy.click()
    atoms(20)
    np.testing.assert_allclose([[a['x'],a['y'],a['z']] for a in window.builder_model['atoms']],original[1],atol=1e-8)
    assert window.builder_active and window.builder_editing
    assert not window.results.isVisible() and not window.timeline_widget.isVisible()
    print('PASS edit selected calculation geometry in Studio Build tab',flush=True)
    window.builder_smiles.setText('CCO')
    window.builder_generate.click()
    atoms(9)
    wait(lambda: not window.builder_state.get('busy'))
    assert [a['el'] for a in window.builder_model['atoms']].count('C')==2
    assert [a['el'] for a in window.builder_model['atoms']].count('H')==6
    np.testing.assert_array_equal(window.calculation.coords,original)
    np.testing.assert_array_equal(window.calculation.energies,energies)
    print('PASS offline SMILES -> ethanol; original energies/trajectory unchanged',flush=True)
    snapshot=json.dumps(window.builder_model,sort_keys=True)
    window.builder_tidy.click()
    wait(lambda: window.builder_state.get('undo',0)>=3 and not window.builder_state.get('busy'))
    window.builder_undo.click()
    wait(lambda: json.dumps(window.builder_model,sort_keys=True)==snapshot)
    window.builder_auto_h.setChecked(False)
    wait(lambda: window.builder_state.get("autoHydrogens") is False)
    window.builder_new.click();atoms(0)
    window.builder_web.setFocus()
    target=window.builder_web.focusProxy() or window.builder_web
    QTest.mouseClick(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(window.builder_web.width()//2,window.builder_web.height()//2))
    atoms(1)
    QTest.keyClick(target,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier);atoms(0)
    QTest.keyClick(target,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier);atoms(1)
    window.builder_elements['O'].click()
    wait(lambda: window.builder_state.get('element')=='O')
    window.builder_tools['bond'].click();wait(lambda:window.builder_state['tool']=='bond')
    drag_atom(0);atoms(2)
    assert window.builder_model['bonds']==[{'a':0,'b':1,'order':1}]
    # Erase an individual bond, then drag between existing atoms to reconnect it.
    window.builder_tools['delete'].click();wait(lambda:window.builder_state['tool']=='delete')
    for _ in range(5): app.processEvents(); time.sleep(.025)
    projected=json.loads(js("JSON.stringify(builderApp.model.atoms.map(a=>{const v=builderApp.view,p=v.camera.position.clone();p.set(a.x,a.y,a.z).project(v.camera);return [(p.x+1)*innerWidth/2,(1-p.y)*innerHeight/2]}))"))
    x,y=[sum(v)/2 for v in zip(*projected)]
    QTest.mouseClick(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(round(x),round(y)))
    wait(lambda:window.builder_state['bonds']==0)
    window.builder_tools['bond'].click();wait(lambda:window.builder_state['tool']=='bond')
    start,end=[QPoint(round(x),round(y)) for x,y in projected]
    QTest.mousePress(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
    QTest.mouseMove(target,end,40);app.processEvents()
    QTest.mouseRelease(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
    wait(lambda:window.builder_state['bonds']==1)
    assert window.builder_state['atoms']==2
    window.builder_undo.click();wait(lambda:window.builder_state['bonds']==0)
    window.builder_undo.click();wait(lambda:window.builder_state['bonds']==1)
    before_move=json.dumps(window.builder_model,sort_keys=True)
    js('builderApp.editor.selection=[0,1];builderApp.editor.update()')
    window.builder_tools['move'].click();wait(lambda:window.builder_state.get('tool')=='move')
    x,y=json.loads(js("JSON.stringify((()=>{const v=builderApp.view,a=builderApp.model.atoms[0],p=v.camera.position.clone();p.set(a.x,a.y,a.z).project(v.camera);return [(p.x+1)*innerWidth/2,(1-p.y)*innerHeight/2]})())"))
    start=QPoint(round(x),round(y));end=start+QPoint(40,25)
    QTest.mousePress(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
    QTest.mouseMove(target,end,30);app.processEvents()
    QTest.mouseRelease(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
    wait(lambda:json.dumps(window.builder_model,sort_keys=True)!=before_move)
    assert 'Distance' in window.builder_measure.text()
    window.builder_undo.click();wait(lambda:json.dumps(window.builder_model,sort_keys=True)==before_move)
    window.builder_tools['delete'].click();wait(lambda:window.builder_state.get('tool')=='delete')
    click_atom(0);atoms(1)
    window.builder_undo.click();atoms(2)
    window.builder_tools['bond'].click();wait(lambda: window.builder_state.get('tool')=='bond')
    window.builder_order.setCurrentIndex(1);wait(lambda:window.builder_state.get('bondOrder')==2)
    js('builderApp.editor.bond(0);builderApp.editor.bond(1)')
    wait(lambda: window.builder_model['bonds'][0]['order']==2)
    window.builder_figure.click()
    wait(lambda: not window.builder_editing)
    wait(lambda: window.viewer_stack.currentWidget()==window.builder_web)
    assert js('builderApp.model.bonds[0].order')==2
    assert js('builderApp.view.overlays.visible') is False
    window.preset.setCurrentText('Paton-inspired')
    wait(lambda: js("builderApp.view.appearance.preset")=='Paton-inspired')
    assert not window.results.isVisible()
    print('PASS native Draw/element controls, bonds, and Studio/Paton figure preview with real bond orders',flush=True)
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        window.export_builder('mol',root/'draft.mol')
        wait(lambda:(root/'draft.mol').exists())
        text=(root/'draft.mol').read_text()
        assert 'V2000' in text and text.splitlines()[6][6:9].strip()=='2'
        window.export_size.setValue(800)
        window.export_samples.setCurrentIndex(0)
        window.transparent.setChecked(True)
        window.render_export(root/'draft.png')
        wait(lambda:(root/'draft.png').exists() and not window.exporting,60)
        image=Image.open(root/'draft.png')
        assert max(image.size)==800 and image.mode=='RGBA'
        assert image.getchannel('A').getextrema()==(0,255)
        window.inspector.setCurrentIndex(0)
        wait(lambda: not window.builder_active)
        wait(lambda: js('sceneState.atoms',False)==20)
        wait(lambda: js('sceneState.surfaces',False)==2)
        assert window.cube is original_cube
        assert window.results.isVisible() and window.timeline_widget.isVisible()
        np.testing.assert_array_equal(window.calculation.coords,original)
        np.testing.assert_array_equal(window.calculation.energies,energies)
        revision=window.builder_state['revision']
        window.open_paths([root/'draft.mol'])
        wait(lambda:not window.busy and window.builder_active and window.builder_state['revision']>revision and window.builder_state['atoms']==2)
        assert window.builder_model['bonds'][0]['order']==2
    # Familiar builder flow: methane -> ethane -> ethanol by replacing terminal H.
    window.builder_auto_h.setChecked(True)
    window.builder_order.setCurrentIndex(0)
    window.builder_elements['C'].click()
    window.builder_new.click();atoms(0);wait(lambda:window.builder_state['tool']=='add')
    target=window.builder_web.focusProxy() or window.builder_web
    QTest.mouseClick(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(window.builder_web.width()//2,window.builder_web.height()//2))
    atoms(5);assert window.builder_state['formula']=='CH₄'
    click_atom(1);atoms(8);assert window.builder_state['formula']=='C₂H₆'
    h=next(b['b'] for b in window.builder_model['bonds'] if b['a']==1 and window.builder_model['atoms'][b['b']]['el']=='H')
    window.builder_elements['O'].click();wait(lambda:window.builder_state.get('element')=='O')
    click_atom(h);atoms(9);assert window.builder_state['formula']=='C₂H₆O'
    ethanol=json.dumps(window.builder_model,sort_keys=True)
    window.builder_undo.click();atoms(8)
    window.builder_redo.click();atoms(9)
    assert json.dumps(window.builder_model,sort_keys=True)==ethanol
    # Attach a benzene ring to the selected hydroxyl oxygen, keeping normal valences.
    window.builder_tools['fragment'].click()
    window.builder_fragment_mode.setCurrentIndex(1)
    wait(lambda:window.builder_state.get('fragmentMode')=='attach')
    window.builder_insert.click();atoms(19)
    wait(lambda:not window.builder_state.get('busy'))
    assert window.builder_state['formula']=='C₈H₁₀O'
    window.builder_undo.click();atoms(9)
    assert json.dumps(window.builder_model,sort_keys=True)==ethanol
    # Shared appearance: atom/bond radii, dark bonds, projection, outlines and AO.
    window.builder_preset.setCurrentText('Studio')
    wait(lambda:js('builderApp.view.camera.isOrthographicCamera') is True)
    assert abs(js("builderApp.view.radius({el:'C'})")-.425)<1e-8
    assert abs(js('builderApp.view.bondRadius()')-.11)<1e-8
    assert js('builderApp.view.bondColor()')=='#424942'
    assert js('builderApp.view.outlineMeshes.every(m=>m.visible)') is True
    window.builder_preset.setCurrentText('Soft studio')
    wait(lambda:js('!!builderApp.view.composer && builderApp.view.appearance.ao') is True)
    js('builderApp.view.invalidate()')
    for _ in range(8): app.processEvents(); time.sleep(.03)
    window.builder_preset.setCurrentText('Studio')
    print('PASS Draw methane -> ethanol, automatic H, fragment attachment, exact undo, shared Studio appearance',flush=True)
    window.builder_smiles.setText('c1ccccc1')
    window.builder_generate.click();atoms(12);wait(lambda:not window.builder_state.get('busy'))
    print('PASS draft MOL + supersampled alpha PNG export, structure import, return to untouched calculation',flush=True)
    js('builderApp.view.invalidate()')
    for _ in range(8): app.processEvents(); time.sleep(.03)
    assert js("builderApp.model.bonds.filter(b=>b.order===2).every(b=>{const a=builderApp.model.atoms[b.a],c=builderApp.model.atoms[b.b],dir=builderApp.view.camera.position.clone().set(c.x-a.x,c.y-a.y,c.z-a.z).normalize();return Math.abs(builderApp.view.bondAxis(dir,b).z)<1e-6})") is True
    # Native area selection and selection rotation share the same pickable scene.
    original_benzene=json.dumps(window.builder_model,sort_keys=True)
    def area_drag(tool,points):
        window.builder_tools[tool].click();wait(lambda:window.builder_state['tool']==tool)
        target=window.builder_web.focusProxy() or window.builder_web
        QTest.mousePress(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,points[0])
        for n,p in enumerate(points[1:],2):
            QTest.mouseMove(target,p,40);app.processEvents()
            if tool=='lasso':wait(lambda:js('builderApp.editor.area?.points.length || 0')>=n)
            else:QTest.qWait(70)
        QTest.mouseRelease(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,points[-1])
        app.processEvents()
    w,h=window.builder_web.width(),window.builder_web.height()
    area_drag('rect',[QPoint(15,15),QPoint(w-20,h-30)])
    wait(lambda:window.builder_state['selection']==12)
    window.builder_command(type='escape');wait(lambda:window.builder_state['selection']==0)
    area_drag('lasso',[QPoint(15,15),QPoint(w-20,15),QPoint(w-20,h-30),QPoint(15,h-30),QPoint(15,15)])
    wait(lambda:window.builder_state['selection']==12)
    area_drag('rotate',[QPoint(w//2,h//2),QPoint(w//2+60,h//2+30)])
    wait(lambda:json.dumps(window.builder_model,sort_keys=True)!=original_benzene)
    window.builder_undo.click()
    wait(lambda:json.dumps(window.builder_model,sort_keys=True)==original_benzene)
    window.builder_command(type='escape');wait(lambda:window.builder_state['tool']=='select')
    print('PASS native rectangle/lasso selection, selection rotation, exact undo',flush=True)
    if len(sys.argv)>1:
        wait(lambda:window.builder_state['selection']==0)
        for _ in range(15):app.processEvents();time.sleep(.03)
        window.grab().save(sys.argv[1])
    print('PASS combined desktop builder smoke test',flush=True)
finally:
    window.close();app.processEvents();workspace.cleanup()
