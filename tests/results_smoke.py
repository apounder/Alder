"""Real-output results, native substitution/attachment, and free rotation regression."""
from dataclasses import replace
import json
from pathlib import Path
import sys,tempfile,time
import numpy as np
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from alder.app import Window,configure_app
from alder.data import BOHR
app=QApplication([]);configure_app(app)
w=Window();w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);w.show();QApplication.setActiveWindow(w)
errors=[];w.bridge.error.connect(errors.append);w.builder_bridge.error.connect(errors.append)
QMessageBox.warning=lambda parent,title,msg:errors.append(msg)
def pump(t=.12):
    stop=time.monotonic()+t
    while time.monotonic()<stop:app.processEvents();time.sleep(.01)
def wait(fn,timeout=35):
    stop=time.monotonic()+timeout
    while time.monotonic()<stop:
        if errors:raise AssertionError(errors)
        if fn():return
        pump(.02)
    raise AssertionError(f'Timeout: {w.builder_state}; {w.statusBar().currentMessage()}')
def js(code,builder=False):
    r=[];(w.builder_web if builder else w.web).page().runJavaScript(code,lambda x:r.append(x));wait(lambda:r);return r[0]
def value(code,builder=False):return json.loads(js('JSON.stringify('+code+')',builder))
def click_atom(index):
    x,y=value(f"(()=>{{const v=builderApp.view,a=builderApp.model.atoms[{index}],p=v.camera.position.clone();v.camera.updateMatrixWorld();p.set(a.x,a.y,a.z).project(v.camera);return [(p.x+1)*innerWidth/2,(1-p.y)*innerHeight/2]}})()",True)
    assert js(f'builderApp.view.pick({{clientX:{x},clientY:{y}}})',True)==index
    target=w.builder_web.focusProxy() or w.builder_web
    QTest.mouseClick(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(round(x),round(y)))
try:
    wait(lambda:w.renderer_ready and w.builder_ready)
    w.inspector.setCurrentIndex(w.build_tab)
    w.builder_new.click();wait(lambda:w.builder_state.get('tool')=='add')
    target=w.builder_web.focusProxy() or w.builder_web
    QTest.mouseClick(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(w.builder_web.width()//2,w.builder_web.height()//2))
    wait(lambda:w.builder_state.get('formula')=='CH₄')
    methane=json.dumps(w.builder_model,sort_keys=True)
    w.builder_tools['select'].click();wait(lambda:w.builder_state['tool']=='select')
    assert w.builder_elements['O'].isVisible()
    w.builder_elements['O'].click();wait(lambda:w.builder_state['tool']=='add' and w.builder_state['element']=='O')
    click_atom(0);wait(lambda:w.builder_state['formula']=='H₂O')
    assert w.builder_model['atoms'][0]['el']=='O' and w.builder_state['atoms']==3
    w.builder_elements['N'].click();wait(lambda:w.builder_state['element']=='N')
    click_atom(0);wait(lambda:w.builder_state['formula']=='H₃N')
    w.builder_elements['C'].click();wait(lambda:w.builder_state['element']=='C')
    click_atom(0);wait(lambda:w.builder_state['formula']=='CH₄')
    # Undo all substitutions restores the original molecule exactly.
    for expected in ('H₃N','H₂O','CH₄'):
        QTest.keyClick(target,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier);wait(lambda:w.builder_state['formula']==expected)
    assert json.dumps(w.builder_model,sort_keys=True)==methane
    # The full periodic table follows the same replacement path, including repeat selection.
    w.builder_more.setCurrentIndex(w.builder_more.findData('Br'));w.builder_more.activated.emit(w.builder_more.currentIndex())
    wait(lambda:w.builder_state['tool']=='add' and w.builder_state['element']=='Br')
    click_atom(0);wait(lambda:w.builder_state['formula']=='HBr')
    assert w.builder_state['atoms']==2
    w.builder_undo.click();wait(lambda:w.builder_state['formula']=='CH₄')
    w.builder_elements['C'].click();wait(lambda:w.builder_state['element']=='C')
    undo=w.builder_state['undo'];click_atom(0);pump();assert w.builder_state['undo']==undo and w.builder_state['formula']=='CH₄'
    w.builder_elements['C'].click();w.builder_tools['add'].click();pump()
    assert w.builder_elements['C'].isChecked() and w.builder_tools['add'].isChecked()
    print('PASS palette clicks substitute O/N/C/Br with adjusted H, no accidental growth, and exact keyboard undo',flush=True)
    w.builder_tools['bond'].click();wait(lambda:w.builder_state['tool']=='bond')
    click_atom(0);wait(lambda:w.builder_state.get('formula')=='C₂H₆')
    ethane=json.dumps(w.builder_model,sort_keys=True)
    w.builder_tools['select'].click();wait(lambda:w.builder_state['tool']=='select')
    w.builder_order.setCurrentIndex(1);wait(lambda:w.builder_state['bondOrder']==2 and w.builder_state['tool']=='add')
    js("(()=>{const v=builderApp.view,[a,b]=builderApp.model.atoms,c=v.camera.position.clone().set((a.x+b.x)/2,(a.y+b.y)/2,(a.z+b.z)/2),d=v.camera.position.clone().set(b.x-a.x,b.y-a.y,b.z-a.z),eye=d.cross(v.camera.position.clone().set(0,0,1)).normalize();v.camera.position.copy(c).addScaledVector(eye,10);v.camera.up.set(0,0,1);v.controls.target.copy(c);v.controls.update();v.invalidate()})()",True);pump()
    x,y=value("(()=>{const v=builderApp.view,[a,b]=builderApp.model.atoms,p=v.camera.position.clone();v.camera.updateMatrixWorld();p.set((a.x+b.x)/2,(a.y+b.y)/2,(a.z+b.z)/2).project(v.camera);return [(p.x+1)*innerWidth/2,(1-p.y)*innerHeight/2]})()",True)
    picked=value(f'builderApp.view.pick({{clientX:{x},clientY:{y}}})',True)
    assert picked is None,(picked,x,y)
    QTest.mouseClick(target,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(round(x),round(y)))
    wait(lambda:w.builder_state['formula']=='C₂H₄')
    assert w.builder_model['bonds'][0]['order']==2
    w.builder_undo.click();wait(lambda:w.builder_state['formula']=='C₂H₆')
    assert json.dumps(w.builder_model,sort_keys=True)==ethane
    w.builder_order.setCurrentIndex(0);wait(lambda:w.builder_state['bondOrder']==1)
    w.builder_elements['O'].click();wait(lambda:w.builder_state['tool']=='add' and w.builder_state['element']=='O')
    w.builder_tools['bond'].click();wait(lambda:w.builder_state['tool']=='bond')
    click_atom(1);wait(lambda:w.builder_state['formula']=='C₂H₆O')
    w.builder_undo.click();wait(lambda:w.builder_state['formula']=='C₂H₆')
    w.builder_undo.click();wait(lambda:w.builder_state['formula']=='CH₄')
    assert json.dumps(w.builder_model,sort_keys=True)==methane
    w.builder_elements['C'].click();w.builder_order.setCurrentIndex(1);wait(lambda:w.builder_state['element']=='C' and w.builder_state['bondOrder']==2)
    w.builder_tools['bond'].click();wait(lambda:w.builder_state['tool']=='bond')
    click_atom(0);wait(lambda:w.builder_state['formula']=='C₂H₄')
    w.builder_undo.click();wait(lambda:w.builder_state['formula']=='CH₄')
    w.builder_order.setCurrentIndex(2);wait(lambda:w.builder_state['bondOrder']==3)
    click_atom(0);wait(lambda:w.builder_state['formula']=='C₂H₂')
    print('PASS native clicks grow methane → ethane → ethanol; double/triple bonds adjust H; exact undo',flush=True)
    # Cross both poles repeatedly. A fixed-up orbit camera cannot pass this test.
    w.builder_tools['select'].click();wait(lambda:w.builder_state['tool']=='select')
    w.send(type='fit');pump()
    ups=[];orientations=[]
    x,y=w.builder_web.width()//2,w.builder_web.height()//2
    for _ in range(10):
        QTest.mousePress(target,Qt.MouseButton.MiddleButton,Qt.KeyboardModifier.NoModifier,QPoint(x,y-100))
        QTest.mouseMove(target,QPoint(x,y+100),60);pump(.06)
        QTest.mouseRelease(target,Qt.MouseButton.MiddleButton,Qt.KeyboardModifier.NoModifier,QPoint(x,y+100));pump(.06)
        ups.append(value('builderApp.view.camera.up.y',True));orientations.append(value('builderApp.view.camera.quaternion.toArray()',True))
    assert min(ups)<-.5 and max(ups)>.5,ups
    assert all(np.linalg.norm(np.array(a)-b)>.1 for a,b in zip(orientations,orientations[1:])),orientations
    pump(.2);frame=js('builderApp.view.frameCount',True);pose=value('builderApp.view.cameraState()',True);pump(.4)
    assert js('builderApp.view.frameCount',True)==frame and pose==value('builderApp.view.cameraState()',True)
    print('PASS repeated free rotation across poles, no momentum or idle frames',flush=True)
    for filename in ('gaussian-freq.log','orca-freq.out'):
        w.open_paths([Path(__file__).parent/'data'/filename]);wait(lambda:not w.busy and w.calculation and w.calculation.name==filename)
        assert w.orbital_table.rowCount()==60 and w.vibration_table.rowCount()==54
        assert 'HOMO' in w.orbital_table.item(34,1).text()
        assert 'LUMO' in w.orbital_table.item(35,1).text()
        assert 'gap' in w.orbital_note.text()
        coords=w.calculation.coords.copy();disps=w.calculation.displacements.copy()
        w.results.setCurrentIndex(w.vibration_tab);w.vibration_table.selectRow(4)
        wait(lambda:value('window.sceneState.vibration') and value('window.sceneState.vibration')['mode']==5)
        assert w.vib_play.isEnabled() and not w.timeline_widget.isEnabled()
        w.vib_play.click();wait(lambda:value('window.sceneState.vibration')['playing'])
        first=value('calculationApp.view.model.atoms');frame=js('calculationApp.view.frameCount')
        wait(lambda:js('calculationApp.view.frameCount')>frame+4)
        assert value('calculationApp.view.model.atoms')!=first
        w.vib_play.click();wait(lambda:not value('window.sceneState.vibration')['playing']);pump(.2)
        v=value('calculationApp.vibration');positions=np.array([[a[k] for k in 'xyz'] for a in value('calculationApp.view.model.atoms')])
        np.testing.assert_allclose(positions,np.array(v['base'])+np.array(v['vectors'])*np.sin(v['phase'])*v['amplitude'],atol=1e-8)
        frame=js('calculationApp.view.frameCount');pump(.4);assert js('calculationApp.view.frameCount')==frame
        w.vib_amplitude.setValue(60);w.vib_speed.setValue(1.2);wait(lambda:value('window.sceneState.vibration')['amplitude']==.6)
        w.vib_reset.click();wait(lambda:abs(js('calculationApp.vibration.phase'))<1e-12)
        positions=np.array([[a[k] for k in 'xyz'] for a in value('calculationApp.view.model.atoms')])
        np.testing.assert_allclose(positions,w.calculation.vibration_coords,atol=1e-8)
        np.testing.assert_array_equal(w.calculation.coords,coords);np.testing.assert_array_equal(w.calculation.displacements,disps)
        with tempfile.TemporaryDirectory() as d:
            for kind in ('orbitals','vibrations'):
                path=Path(d)/(kind+'.csv');w.export_results(kind,path);assert path.exists() and len(path.read_text().splitlines())>50
        # Modes without vectors remain inspectable; imaginary modes are explicit.
        saved=w.calculation
        w.calculation=replace(saved,displacements=None);w.refresh_results();assert not w.vib_play.isEnabled()
        imaginary=saved.frequencies.copy();imaginary[0]=-abs(imaginary[0])
        w.calculation=replace(saved,frequencies=imaginary);w.refresh_results();assert 'Imaginary' in w.vibration_note.text()
        w.calculation=saved;w.refresh_results()
        w.vib_play.click();wait(lambda:value('window.sceneState.vibration')['playing'])
        w.results.setCurrentIndex(0);wait(lambda:value('window.sceneState.vibration') is None)
        assert w.timeline_widget.isEnabled()
        np.testing.assert_array_equal(w.calculation.coords,coords)
        print('PASS '+filename+': MO levels, 54 modes, live animation, pause/reset, missing vectors, imaginary labels, CSV, unchanged geometry',flush=True)
    # A rotated cube must rotate the mode geometry and its vectors together.
    calc=w.calculation
    rotation=np.array([[0.,0.,1.],[1.,0.,0.],[0.,1.,0.]])
    translation=np.array([2.,-1.,3.])
    points=(calc.coords[-1]@rotation+translation)/BOHR
    with tempfile.TemporaryDirectory() as d:
        origin=points[0]-2
        x,y,z=np.meshgrid(*(origin[i]+np.arange(9)*.5 for i in range(3)),indexing='ij')
        field=(z-points[0,2])*np.exp(-((x-points[0,0])**2+(y-points[0,1])**2+(z-points[0,2])**2))
        lines=['Synthetic rotated field','Animation registration regression',f'{len(points)} '+ ' '.join(map(str,origin)),
               '9 .5 0 0','9 0 .5 0','9 0 0 .5']
        lines += [f'{atom} 0 '+ ' '.join(map(str,point)) for atom,point in zip(calc.atomnos,points)]
        lines += [' '.join(map(str,field.flat))]
        path=Path(d)/'rotated.cube';path.write_text('\n'.join(lines))
        w.open_paths([path]);wait(lambda:not w.busy and w.cube is not None)
        wait(lambda:value('window.sceneState.surfaces')==2)
        w.inspector.setCurrentIndex(0);w.results.setCurrentIndex(w.vibration_tab);w.vibration_table.selectRow(4)
        wait(lambda:value('window.sceneState.vibration') and value('window.sceneState.vibration')['mode']==5)
        assert value('window.sceneState.surfaces')==0
        v=value('calculationApp.vibration')
        np.testing.assert_allclose(v['base'],calc.vibration_coords@rotation+translation,atol=1e-8)
        vectors=calc.displacements[4]@rotation
        np.testing.assert_allclose(v['vectors'],vectors/np.linalg.norm(vectors,axis=1).max(),atol=1e-8)
        w.results.setCurrentIndex(0);wait(lambda:value('window.sceneState.surfaces')==2)
        w.clear_cube()
    print('PASS cube registration rotates mode vectors; static surfaces hide and restore',flush=True)
    w.open_paths([Path(__file__).parent/'data/gaussian-opt.log']);wait(lambda:not w.busy and w.calculation.name=='gaussian-opt.log')
    assert w.vibration_table.rowCount()==0 and not w.vib_play.isEnabled()
    assert w.orbital_table.rowCount()==60 and w.table.rowCount()==5
    print('PASS optimization energies retained; files without modes clearly disable animation',flush=True)
    w.open_paths([Path(__file__).parent/'data/gaussian-unrestricted.log']);wait(lambda:not w.busy and w.calculation.name=='gaussian-unrestricted.log')
    assert w.orbital_table.rowCount()==120
    assert w.orbital_table.item(34,0).text()=='Alpha' and 'HOMO' in w.orbital_table.item(34,1).text()
    assert w.orbital_table.item(93,0).text()=='Beta' and 'HOMO' in w.orbital_table.item(93,1).text()
    w.orbital_units.setCurrentText('Eh');assert float(w.orbital_table.item(34,3).text())<0
    w.orbital_units.setCurrentText('eV')
    print('PASS unrestricted alpha/beta orbital levels and unit conversion',flush=True)
    if len(sys.argv)>1:
        w.open_paths([Path(__file__).parent/'data/gaussian-freq.log']);wait(lambda:not w.busy and w.calculation.name=='gaussian-freq.log')
        w.results.setCurrentIndex(w.vibration_tab);w.vibration_table.selectRow(10);pump(.5);w.grab().save(sys.argv[1])
finally:w.close();app.processEvents()
