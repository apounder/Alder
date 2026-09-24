"""Desktop integration: multiple outputs, aligned colors/export, setup, and MLIP trajectory."""
import json
from pathlib import Path
import sys
import tempfile
import time

import numpy as np
from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from ase.io.trajectory import Trajectory
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from alder.app import Window, configure_app
from alder.data import read_calculation
from alder.job_setup import open_setup

app=QApplication([]); configure_app(app)
w=Window(); w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True); w.show()
errors=[]
cancel_commands=[]
w.bridge.command.connect(lambda text: cancel_commands.append(text) if json.loads(text).get('type')=='exportCancel' else None)
w.bridge.error.connect(errors.append);w.builder_bridge.error.connect(errors.append)
QMessageBox.warning=lambda parent,title,message: errors.append(message)
def pump(seconds=.1):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.01)
def wait(fn,timeout=45):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if errors:raise AssertionError(errors)
        if fn():return
        pump(.02)
    dialog=getattr(w,'export_dialog',None)
    raise AssertionError('Timed out: '+(dialog.labelText() if dialog else w.statusBar().currentMessage()))
def js(code):
    result=[];w.web.page().runJavaScript(code,lambda value:result.append(value));wait(lambda:result);return result[0]
try:
    wait(lambda:w.renderer_ready and w.builder_ready)
    data=Path(__file__).parent/'data'
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        calc=read_calculation(data/'gaussian-opt.log')
        original=calc.coords.copy()
        rotation=np.array([[0,-1,0],[1,0,0],[0,0,1.]])
        rotated=calc.coords[-1]@rotation+[8,2,-3]
        second=root/'rotated.xyz'; second.write_text(calc.xyz(0,rotated[None]))
        shifted=rotated.copy();shifted[0]+=[.2,.1,-.1]
        third=root/'deformed.xyz'; third.write_text(calc.xyz(0,shifted[None]))
        w.open_paths([data/'gaussian-opt.log',second,third])
        wait(lambda:not w.busy and len(w.documents)==3)
        wait(lambda:js('sceneState.structures')==3)
        assert w.comparison_active
        assert w.comparison_results[1][6]<1e-7 and w.comparison_results[1][5]>1
        assert w.comparison_results[2][6]>.01
        assert js('new Set(calculationApp.view.model.atoms.map(a=>a.structureColor)).size')==3
        assert js('calculationApp.view.model.bonds.every(b=>calculationApp.view.model.atoms[b.a].structureIndex===calculationApp.view.model.atoms[b.b].structureIndex)')
        assert js('calculationApp.view.bondColor(calculationApp.view.model.atoms[0])')=='#4477aa'
        np.testing.assert_array_equal(w.documents[0]['calculation'].coords,original)
        camera=js('calculationApp.view.cameraState()')
        w.compare_solid.setChecked(False);pump()
        assert js('calculationApp.view.model.atoms.every(a=>a.structureColor===null)')
        w.compare_solid.setChecked(True);pump()
        assert camera==js('calculationApp.view.cameraState()')
        w.compare_align.setChecked(False);pump()
        assert abs(js('calculationApp.view.model.atoms[20].x')-rotated[0,0])<1e-7
        w.compare_align.setChecked(True);pump()
        w.compare_table.item(2,0).setCheckState(Qt.CheckState.Unchecked);pump()
        assert js('sceneState.atoms')==40
        w.compare_table.item(2,0).setCheckState(Qt.CheckState.Checked);pump()
        w.inspector.setCurrentIndex(2);pump()
        assert w.comparison_active and js('sceneState.atoms')==60
        w.export_size.setValue(600);w.export_samples.setCurrentIndex(1);w.transparent.setChecked(True)
        image=root/'overlay.png';w.render_export(image);wait(lambda:image.exists() and not w.exporting)
        with Image.open(image) as png:
            assert max(png.size)==600 and png.convert('RGBA').getpixel((0,0))[3]==0
        assert js('sceneState.atoms')==60
        w.export_engine.setCurrentIndex(1);w.ray_samples.setValue(2)
        w.export_size.setMinimum(64);w.export_size.setValue(128)
        ray_image=root/'overlay-ray.png';w.render_export(ray_image)
        wait(lambda:ray_image.exists() and not w.exporting,240)
        with Image.open(ray_image) as png:
            assert max(png.size)==128 and png.getchannel('A').getextrema()==(0,255)
        assert not cancel_commands, 'Successful exports must not send a cancel for the following job.'
        w.export_engine.setCurrentIndex(0)
        w.inspector.setCurrentIndex(0);pump()
        w.calculation_picker.setCurrentIndex(0);pump()
        assert w.calculation.name=='gaussian-opt.log' and not w.comparison_active
        w.slider.setValue(1);w.calculation_picker.setCurrentIndex(1);w.calculation_picker.setCurrentIndex(0)
        assert w.step==1
        w.trajectory_speed.setValue(2);assert w.timer.interval()==175
        w.trajectory_speed.setValue(.5);assert w.timer.interval()==700
        open_setup(w);dialog=w.setup_dialog
        assert 'Gaussian'==dialog.controls['engine'].currentText()
        dialog.controls['engine'].setCurrentText('ORCA')
        assert '%maxcore 1638' in dialog.preview.toPlainText()
        target=root/'calculation.inp'
        QFileDialog.getSaveFileName=lambda *args,**kwargs:(str(target),'')
        dialog.save();assert target.read_text()==dialog.preview.toPlainText()
        dialog.close()
        trajectory=root/'sella.traj'
        with Trajectory(str(trajectory),'w') as writer:
            for shift in [0,.1,.2]:
                atoms=Atoms('OH2',positions=[[0,0,0],[.97+shift,0,0],[-.24,.94,0]])
                atoms.calc=SinglePointCalculator(atoms,energy=-10-shift,forces=np.zeros((3,3)))
                writer.write(atoms)
        w.open_paths([trajectory]);wait(lambda:not w.busy and w.calculation.name=='sella.traj')
        assert len(w.calculation.coords)==3 and w.energy_profile_title.text()=='Potential energy'
        assert w.calculation.energies[-1]<w.calculation.energies[0]
        assert 'eV/Å' in w.convergence_label.text()
        w.trajectory_speed.setValue(10);w.slider.setValue(0);w.play.setChecked(True)
        wait(lambda:w.step!=0);w.play.setChecked(False)
        assert len(w.documents)==4
        w.inspector.setCurrentIndex(w.compare_tab);pump()
        assert 'Atom identities/order differ' in w.compare_report.text()
        w.compare_table.selectRow(3);w.remove_comparison_document();pump()
        assert len(w.documents)==3 and w.calculation is not None
        wait(lambda:js('sceneState.structures')==3)
        # Changing the reference invalidates explicit pairs. Removing an earlier
        # document must retain the same reference object at its new index.
        w.compare_table.selectRow(1);w.compare_mapping.setText('1:1, 2:2, 3:3')
        w.comparison_mapping_changed();w.compare_reference.setCurrentIndex(2)
        assert all(not entry['mapping'] for entry in w.documents)
        reference=w.documents[2]['calculation']
        w.compare_table.selectRow(0);w.remove_comparison_document();pump()
        assert w.documents[w.compare_reference.currentIndex()]['calculation'] is reference
        if len(sys.argv)>1:
            w.grab().save(sys.argv[1])
    print('PASS: multi-output overlay, proper alignment/RMSD, independent colors, no cross-structure bonds, transparent export, document/frame retention, speed, input setup/save, ASE/Sella trajectory and energy/force display.',flush=True)
finally:
    w.close();app.processEvents()
