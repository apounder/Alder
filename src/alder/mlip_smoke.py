"""Packaged-app check using a separate real calculator environment and public weights."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import traceback


def run(report_path, python=None, cache=None):
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .app import Window, configure_app
    from .mlip_ui import MLIPDialog
    from .mlip.offline import bundle_directory
    from PySide6.QtGui import QPalette
    from .mlip_results import calculation_page
    report={'ok':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[]}
    original_home=os.environ.get('ALDER_MLIP_HOME')
    root=Path(tempfile.mkdtemp(prefix='studio-mlip-check-'));os.environ['ALDER_MLIP_HOME']=str(root)
    app=QApplication.instance() or QApplication([]);configure_app(app)
    w=Window();w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);w.show()
    errors=[];warning=QMessageBox.warning;information=QMessageBox.information
    QMessageBox.warning=lambda parent,title,message:errors.append(str(message))
    QMessageBox.information=lambda parent,title,message:errors.append(str(message))
    w.bridge.error.connect(errors.append);w.builder_bridge.error.connect(errors.append)
    d=MLIPDialog(w);w.mlip_dialog=d;d.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);d.show()
    def wait(check,timeout=180):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
            if errors:raise AssertionError(errors)
            if check():return
        raise AssertionError('Timed out: '+d.readiness.text())
    def save(label):
        report['checks'].append(label);Path(report_path).write_text(json.dumps(report,indent=2),encoding='utf-8')
    try:
        wait(lambda:w.renderer_ready and w.builder_ready)
        assert d.job.count()==11 and Path(w.mlip_manager.worker()).is_file()
        save('Native MLIP setup, all job types, and packaged external worker sources')
        assert d.setup_log.palette().color(QPalette.ColorRole.Base).lightness()>220
        save('Light native calculation fields and read-only setup log')
        offline=bundle_directory() is not None
        if (python and cache) or offline:
            d.backend.setCurrentText('aimnet2')
            if offline or os.environ.get('MLIP_SMOKE_AUTO_SETUP')=='1':
                d.automatic_setup()
                wait(lambda:not d.setup_busy(),timeout=1800)
                assert d.check_results,d.readiness.text()+'\n'+d.setup_log.toPlainText()[-8000:]
                save('One-click fresh AIMNet2 setup: '+('bundled offline Python/packages/weights' if offline else 'managed online downloads')+' and real readiness check')
                d.automatic_setup();wait(lambda:not d.setup_busy(),timeout=180)
                assert d.check_results,d.readiness.text()
                save('Repeated automatic setup reuses the installed environment and cached checkpoint')
            elif os.environ.get('MLIP_SMOKE_SETUP')=='1':
                shutil.copytree(Path(cache)/'aimnet2',root/'models'/'aimnet2')
                d.setup_environment()
                wait(lambda:not d.setup_busy() and bool(w.mlip_manager.config.get('aimnet2',{}).get('probe')),timeout=1200)
                save('In-app managed environment installation from the frozen application')
            else:
                shutil.copytree(Path(cache)/'aimnet2',root/'models'/'aimnet2')
                d.environment_path.setText(str(python));d.probe_environment();wait(lambda:d.control_process is None)
            assert w.mlip_manager.config['aimnet2']['probe']['ready'],d.readiness.text()
            d.model_action('check');wait(lambda:d.control_process is None);assert d.check_results,d.readiness.text()
            save('External environment probe and real AIMNet2 checkpoint/device check')
            # Restart the desktop: configured environments persist, readiness does not.
            d.close();w.close();app.processEvents();w=Window()
            w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);w.show()
            w.bridge.error.connect(errors.append);w.builder_bridge.error.connect(errors.append)
            d=MLIPDialog(w);w.mlip_dialog=d;d.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);d.show()
            wait(lambda:w.renderer_ready and w.builder_ready)
            d.backend.setCurrentText('aimnet2');assert not d.check_results
            water=dict(name='Water check',numbers=[8,1,1],positions=[[0,0,0],[.96,0,0],[-.24,.93,0]],charge=0,multiplicity=1)
            d.structure=water;d.job.setCurrentIndex(d.job.findData('optfreq'));d.fields['steps'].setValue(100);d.fields['fmax'].setValue(.02);d.submit()
            wait(lambda:not d.setup_busy());assert d.check_results,d.readiness.text()
            ident=d.selected_job();save('Queue after desktop restart automatically checks the cached model and submits the captured input')
            wait(lambda:w.mlip_manager.store.job(ident)['status'] in ('completed','failed','unconverged'))
            assert w.mlip_manager.store.job(ident)['status']=='completed',w.mlip_manager.store.job(ident)
            child=w.mlip_manager.store.artifact(ident,'workflow')['child']
            calc=calculation_page(w.mlip_manager.store,child);w.add_document(calc);w.activate_calculation(calc)
            assert len(calc.frequencies)==3 and np.isnan(calc.ir_intensities).all() and np.isnan(calc.raman_activities).all()
            w.results.setCurrentIndex(w.vibration_tab);w.vibration_table.selectRow(0);w.vib_play.setChecked(True)
            app.processEvents();assert calc.displacements.shape==(3,3,3)
            w.vib_play.setChecked(False)
            save('Queued optimization → frequency child, Hartree result adapter, unavailable intensities, normal modes')
            d.structure=water;d.job.setCurrentIndex(d.job.findData('md'));d.fields['steps'].setValue(100000);d.fields['stride'].setValue(1);d.submit();md=d.selected_job()
            wait(lambda:w.mlip_manager.store.count(md)>=3);w.mlip_manager.cancel(md)
            wait(lambda:w.mlip_manager.store.job(md)['status']=='cancelled' and w.mlip_manager.process is None)
            assert w.mlip_manager.store.artifact(md,'checkpoint')['exact']
            page=calculation_page(w.mlip_manager.store,md,limit=2);assert len(page.coords)==2
            save('Responsive desktop cancellation, persisted exact MD checkpoint, bounded trajectory page')
            recovery=w.mlip_manager.store.submit(w.mlip_manager.store.job(md)['input'])
            wait(lambda:w.mlip_manager.store.count(recovery)>=2)
            w.mlip_manager.process.kill()
            wait(lambda:w.mlip_manager.store.job(recovery)['status']=='interrupted' and w.mlip_manager.process is None)
            d.close();w.close();app.processEvents();w=Window()
            assert w.mlip_manager.store.job(recovery)['status']=='interrupted'
            assert w.mlip_manager.store.job(md)['status']=='cancelled' and w.mlip_manager.store.count(child)>0
            save('History and interrupted-job recovery after desktop restart')
        else:
            report['unavailable']='Real-worker checks require an existing AIMNet2 environment and cached public weights.'
        report['ok']=True
    except Exception:
        report['error']=traceback.format_exc()
        report['setup_log']=d.setup_log.toPlainText()[-8000:]
    finally:
        if d.control_process:
            d.control_process.kill();d.control_process.waitForFinished(3000);d.control_process=None
        d.close();w.close();app.processEvents()
        QMessageBox.warning=warning;QMessageBox.information=information
        Path(report_path).write_text(json.dumps(report,indent=2),encoding='utf-8')
        if original_home is None:os.environ.pop('ALDER_MLIP_HOME',None)
        else:os.environ['ALDER_MLIP_HOME']=original_home
    return 0 if report['ok'] else 1
