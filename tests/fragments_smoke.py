"""Native fragment preview, atom replacement, spiro junction, and ester regression."""
import json
from pathlib import Path
import sys, tempfile, time
from rdkit import Chem
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from alder.app import Window, configure_app
from alder.structure import molecule_from_model
app=QApplication([]);configure_app(app)
w=Window();w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);w.show();QApplication.setActiveWindow(w)
errors=[];w.builder_bridge.error.connect(errors.append);w.bridge.error.connect(errors.append)
QMessageBox.warning=lambda parent,title,message:errors.append(message)

def pump(seconds=.15):
    stop=time.monotonic()+seconds
    while time.monotonic()<stop:app.processEvents();time.sleep(.01)
def wait(fn,timeout=35):
    stop=time.monotonic()+timeout
    while time.monotonic()<stop:
        if errors:raise AssertionError(errors)
        if fn():return
        pump(.02)
    raise AssertionError((w.builder_state,w.statusBar().currentMessage()))
def js(code):
    result=[];w.builder_web.page().runJavaScript(code,lambda value:result.append(value));wait(lambda:result);return result[0]
def value(code):return json.loads(js('JSON.stringify('+code+')'))
def choose(name):
    w.builder_tools['fragment'].click()
    w.builder_fragment.setCurrentIndex(w.builder_fragment.findData(name))
    wait(lambda:w.builder_state.get('tool')=='fragment' and w.builder_state.get('fragment')==name)
def target_atom(hydrogen=False):
    # Pick an unobscured atom in the actual displayed orientation.
    condition="a.el!=='H'" if hydrogen else "a.el==='H'"
    return value("(()=>{const v=builderApp.view;v.camera.updateMatrixWorld();for(let i=0;i<builderApp.model.atoms.length;i++){const a=builderApp.model.atoms[i];if("+condition+")continue;const p=v.camera.position.clone().set(a.x,a.y,a.z).project(v.camera),x=(p.x+1)*innerWidth/2,y=(1-p.y)*innerHeight/2;if(v.pick({clientX:x,clientY:y})===i)return [i,x,y]}})()")
def click(index,x,y):
    assert value(f'builderApp.view.pick({{clientX:{x},clientY:{y}}})')==index
    QTest.mouseClick(w.builder_web.focusProxy() or w.builder_web,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(round(x),round(y)))
def place(name):
    w.builder_new.click();wait(lambda:w.builder_state['atoms']==0)
    choose(name);w.builder_place_fragment.click();wait(lambda:w.builder_state['atoms']>0)
    pump()
try:
    wait(lambda:w.builder_ready and w.renderer_ready)
    w.inspector.setCurrentIndex(w.build_tab)
    place('Cyclohexane');assert w.builder_state['formula']=='C₆H₁₂'
    original=json.dumps(w.builder_model,sort_keys=True)
    assert js('typeof window.initRDKitModule')=='undefined'
    choose('Cyclopentane');index,x,y=target_atom()
    target=w.builder_web.focusProxy() or w.builder_web
    QApplication.sendEvent(target,QMouseEvent(QEvent.Type.MouseMove,QPointF(x,y),QPointF(target.mapToGlobal(QPoint(round(x),round(y)))),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier))
    wait(lambda:js('!!builderApp.view.fragmentPreview'))
    assert json.dumps(w.builder_model,sort_keys=True)==original
    assert js('builderApp.view.fragmentPreview.children.every(m=>m.isInstancedMesh)')
    pump();frames=js('builderApp.view.frameCount');pump(.35);assert js('builderApp.view.frameCount')==frames
    if len(sys.argv)>1:w.grab().save(sys.argv[1])
    click(index,x,y);wait(lambda:w.builder_state['formula']=='C₁₀H₁₈')
    assert not js('!!builderApp.view.fragmentPreview')
    molecule=Chem.RemoveHs(molecule_from_model(w.builder_model))
    rings=[set(r) for r in Chem.GetSymmSSSR(molecule)]
    assert sorted(map(len,rings))==[5,6] and len(rings[0]&rings[1])==1
    if len(sys.argv)>1:
        pump();w.grab().save(str(Path(sys.argv[1]).with_stem('spiro-preview')))
    spiro=json.dumps(w.builder_model,sort_keys=True)
    w.builder_undo.click();wait(lambda:json.dumps(w.builder_model,sort_keys=True)==original)
    w.builder_redo.click();wait(lambda:json.dumps(w.builder_model,sort_keys=True)==spiro)
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'spiro.mol';w.export_builder('mol',path);wait(path.exists)
        exported=Chem.MolFromMolBlock(path.read_text());assert exported is not None
        assert Chem.MolToSmiles(exported)==Chem.MolToSmiles(molecule)
    print('PASS native hover preview, no WASM, zero idle frames, spiro[4.5] topology, exact undo/redo, MOL export',flush=True)
    w.builder_hydrogens.setChecked(False);wait(lambda:js('builderApp.view.style.hydrogens') is False)
    # Choose the joining atom by clicking the real depiction, then attach each ester orientation.
    for name,root_el in [('Methyl ester · carbonyl side','C'),('Acetoxy ester · oxygen side','O')]:
        place('Methyl');choose(name)
        preview=w.builder_fragment_preview;rect=preview.drawing_rect()
        px,py=preview.points[2]
        QTest.mouseClick(preview,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(round(rect.x()+px*rect.width()/320),round(rect.y()+py*rect.height()/160)))
        wait(lambda:w.builder_state.get('fragmentRoot')==2)
        assert preview.root==2
        w.builder_fragment_root.setCurrentIndex(0);wait(lambda:w.builder_state['fragmentRoot']==0)
        w.builder_fragment_mode.setCurrentIndex(1);wait(lambda:w.builder_state.get('fragmentMode')=='attach')
        index,x,y=target_atom();click(index,x,y);wait(lambda:w.builder_state['formula']=='C₃H₆O₂')
        model=w.builder_model;neighbours=[b['b'] if b['a']==index else b['a'] for b in model['bonds'] if index in (b['a'],b['b'])]
        assert [model['atoms'][i]['el'] for i in neighbours if model['atoms'][i]['el']!='H']==[root_el]
        assert Chem.MolToSmiles(Chem.RemoveHs(molecule_from_model(model)))=='COC(C)=O'
    # A fragment click can replace a terminal atom and extend the chain by one C.
    w.builder_fragment_mode.setCurrentIndex(0)
    place('Ethyl');before=json.dumps(w.builder_model,sort_keys=True);index,x,y=target_atom();click(index,x,y)
    wait(lambda:w.builder_state['formula']=='C₃H₈')
    assert Chem.MolToSmiles(Chem.RemoveHs(molecule_from_model(w.builder_model)))=='CCC'
    w.builder_undo.click();wait(lambda:json.dumps(w.builder_model,sort_keys=True)==before)
    js('builderApp.editor.selection=[0,1];builderApp.editor.update()');wait(lambda:w.builder_state['selection']==2)
    assert not w.builder_insert.isEnabled() # no silent, disconnected insertion for an ambiguous selection
    QTest.keyClick(w.builder_web.focusProxy() or w.builder_web,Qt.Key.Key_Escape)
    wait(lambda:w.builder_state['tool']=='select');assert not js('!!builderApp.view.fragmentPreview')
    assert js('typeof window.initRDKitModule')=='undefined'
    print('PASS clickable joining atoms, both ester directions, terminal chain replacement, selection safeguards, Escape',flush=True)
    w.builder_hydrogens.setChecked(True);wait(lambda:js('builderApp.view.style.hydrogens') is True)
    for auto_h in (False,True):
        w.builder_auto_h.setChecked(auto_h);wait(lambda:w.builder_state.get('autoHydrogens')==auto_h)
        for name,expected in [('Methyl','CC'),('Benzene','Cc1ccccc1'),('Methyl ester · carbonyl side','COC(C)=O'),('Acetoxy ester · oxygen side','COC(C)=O')]:
            place('Methyl');before=json.dumps(w.builder_model,sort_keys=True)
            choose(name);index,x,y=target_atom(hydrogen=True)
            revision=w.builder_state['revision'];click(index,x,y)
            wait(lambda:w.builder_state['revision']>revision)
            assert not js('!!builderApp.view.fragmentPreview')
            molecule=molecule_from_model(w.builder_model);Chem.SanitizeMol(molecule)
            assert Chem.MolToSmiles(Chem.RemoveHs(molecule))==expected,(name,auto_h)
            assert js('builderApp.view.atomMesh.count')==w.builder_state['atoms']
            after=json.dumps(w.builder_model,sort_keys=True)
            wait(w.builder_undo.isEnabled)
            w.builder_undo.click();wait(lambda:json.dumps(w.builder_model,sort_keys=True)==before)
            wait(w.builder_redo.isEnabled)
            w.builder_redo.click();wait(lambda:json.dumps(w.builder_model,sort_keys=True)==after)
    print('PASS real C–H clicks: methyl, aromatic and both ester junctions, automatic H on/off, rendered atom counts, exact undo/redo',flush=True)
    w.builder_hydrogens.setChecked(False)
    w.builder_fragment_mode.setCurrentIndex(1)
    for name,root,expected in [('Vinyl',1,'C=CC'),('Pyrrole',3,'Cn1cccc1'),('Propyl',1,'CC(C)C')]:
        place('Methyl');choose(name)
        preview=w.builder_fragment_preview;rect=preview.drawing_rect();px,py=preview.points[root]
        QTest.mouseClick(preview,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(round(rect.x()+px*rect.width()/320),round(rect.y()+py*rect.height()/160)))
        wait(lambda:w.builder_state.get('fragmentRoot')==root)
        index,x,y=target_atom();revision=w.builder_state['revision'];click(index,x,y)
        wait(lambda:w.builder_state['revision']>revision)
        molecule=molecule_from_model(w.builder_model);Chem.SanitizeMol(molecule)
        assert Chem.MolToSmiles(Chem.RemoveHs(molecule))==expected,(name,root)
        if name=='Vinyl':
            from rdkit.Chem import rdMolTransforms
            junction=next(b['b'] if b['a']==index else b['a'] for b in w.builder_model['bonds'] if index in (b['a'],b['b']) and w.builder_model['atoms'][b['b'] if b['a']==index else b['a']]['el']!='H')
            other=next(a.GetIdx() for a in molecule.GetAtomWithIdx(junction).GetNeighbors() if a.GetIdx()!=index and a.GetSymbol()!='H')
            assert 115<rdMolTransforms.GetAngleDeg(molecule.GetConformer(),index,junction,other)<125
    print('PASS non-default preview joining atoms: vinyl geometry, pyrrole nitrogen and branched propyl; RDKit valences',flush=True)
finally:w.close();app.processEvents()
