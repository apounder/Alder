"""Setup branches use real Qt process chaining; downloads/auth are simulated here."""
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest
from molecule_studio.mlip import environment


@pytest.fixture
def setup_dialog(monkeypatch,tmp_path):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication,QWidget
    from molecule_studio import mlip_ui as ui
    app=QApplication.instance() or QApplication([])
    window=QWidget();window.mlip_manager=ui.JobManager(window,tmp_path/'data with spaces')
    dialog=ui.MLIPDialog(window);dialog.backend.setCurrentText('aimnet2')
    worker=tmp_path/'fake_worker.py'
    worker.write_text('''import argparse,json,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('action')
for name in ('result','backend','config','cache','structure'):p.add_argument('--'+name)
p.add_argument('--licensed',action='store_true');a=p.parse_args()
root=Path(a.result).parent
with (root/'calls').open('a') as f:f.write(a.action+'\\n')
scenario=json.loads((root/'scenario.json').read_text())
if a.action=='probe':result={'ready':True,'devices':['cpu'],'sella':True}
elif a.action=='availability':result={'cached':scenario.get('cached',False),'licensed':scenario.get('licensed',False),'authenticated':scenario.get('authenticated',True)}
elif a.action=='login':
    assert sys.stdin.readline().startswith('hf_');print('hf_EXAMPLESECRET');result={'connected':True}
elif a.action=='download':
    if scenario.get('licensed'):assert a.licensed
    if scenario.get('slow'):time.sleep(30)
    result={'error':'Simulated download failure'} if scenario.get('fail') else {'sha256':'a'*64}
else:
    if scenario.get('slow_check'):time.sleep(30)
    result={'ready':False,'error':'Simulated model failure'} if scenario.get('fail_check') else {'ready':True,'sha256':'a'*64}
Path(a.result).write_text(json.dumps(result))
''')
    monkeypatch.setattr(window.mlip_manager,'worker',lambda:str(worker))
    installations=[]
    def install(root,backend,emit,cancelled):
        installations.append(backend);return sys.executable
    monkeypatch.setattr(ui,'managed_environment',install)
    root=window.mlip_manager.root
    def scenario(**kw):(root/'scenario.json').write_text(json.dumps(kw))
    def calls():return (root/'calls').read_text().splitlines() if (root/'calls').exists() else []
    def wait(check):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            app.processEvents()
            if check():return
            time.sleep(.01)
        pytest.fail(dialog.readiness.text()+'; calls='+repr(calls()))
    scenario()
    yield SimpleNamespace(dialog=dialog,ui=ui,root=root,scenario=scenario,calls=calls,wait=wait,installations=installations)
    dialog.stop_setup();wait(lambda:not dialog.setup_busy())
    dialog.close();window.mlip_manager.shutdown();window.close();app.processEvents()


def test_one_click_fresh_setup_cached_retry_and_configuration_lock(setup_dialog):
    t=setup_dialog;d=t.dialog
    d.automatic_setup()
    assert not d.backend.isEnabled() and not d.auto_button.isEnabled()
    t.wait(lambda:not d.setup_busy())
    assert t.calls()==['probe','availability','download','check']
    assert t.installations==['aimnet2']
    assert d.model_key(d.model_config()) in d.check_results
    assert d.manager.preparing is None and d.auto_button.isEnabled()
    t.scenario(cached=True)
    d.automatic_setup();t.wait(lambda:not d.setup_busy())
    assert t.calls()[-3:]==['probe','availability','check']
    assert t.installations==['aimnet2']
    assert d.manager.python('aimnet2')==sys.executable


def test_failed_download_and_cancellation_can_retry(setup_dialog):
    t=setup_dialog;d=t.dialog;t.scenario(fail=True)
    d.automatic_setup();t.wait(lambda:not d.setup_busy())
    assert not d.check_results and 'failed' in d.readiness.text()
    t.scenario(slow=True);d.automatic_setup()
    t.wait(lambda:t.calls().count('download')==2)
    d.stop_setup();t.wait(lambda:not d.setup_busy())
    assert 'stopped' in d.readiness.text() and not d.check_results
    t.scenario();d.automatic_setup();t.wait(lambda:not d.setup_busy())
    assert d.check_results and t.installations==['aimnet2']


def test_gated_login_chain_and_secret_redaction(setup_dialog,monkeypatch):
    t=setup_dialog;d=t.dialog;d.backend.setCurrentText('uma')
    t.scenario(licensed=True,authenticated=False)
    # UI acknowledgement only; the test never requests real gated weights.
    d.license_ack.setChecked(True)
    monkeypatch.setattr(d,'huggingface_login',lambda callback:d.control('login',[],callback,secret='hf_EXAMPLESECRET'))
    d.automatic_setup();t.wait(lambda:not d.setup_busy())
    assert t.calls()==['probe','availability','login','download','check']
    assert 'hf_EXAMPLESECRET' not in d.setup_log.toPlainText()
    assert 'hf_EXAMPLESECRET' not in d.manager.config_file.read_text()
    assert 'hf_EXAMPLESECRET' not in (t.root/'model-check.json').read_text()
    assert d.check_results


def test_declining_restricted_download_retains_environment(setup_dialog,monkeypatch):
    t=setup_dialog;d=t.dialog;d.backend.setCurrentText('uma');t.scenario(licensed=True,authenticated=False)
    monkeypatch.setattr(t.ui.QMessageBox,'exec',lambda _:t.ui.QMessageBox.StandardButton.Cancel)
    d.automatic_setup();t.wait(lambda:not d.setup_busy())
    assert t.calls()==['probe','availability'] and not d.check_results
    assert d.manager.python('uma')==sys.executable and 'pending' in d.readiness.text()


def test_unavailable_device_does_not_silently_switch_to_cpu(setup_dialog):
    t=setup_dialog;d=t.dialog;d.device.addItem('cuda');d.device.setCurrentText('cuda')
    d.automatic_setup();t.wait(lambda:not d.setup_busy())
    assert t.calls()==['probe'] and not d.check_results
    assert 'device is unavailable' in d.readiness.text()


@pytest.mark.parametrize('outcome',['ready','failed','cancelled'])
def test_queue_rechecks_after_reopen_and_preserves_input(setup_dialog,outcome):
    t=setup_dialog;d=t.dialog
    d.manager.timer.stop()  # Inspect queued input without running the simulated calculator.
    d.manager.config['aimnet2']={'python':sys.executable,'probe':{'ready':True,'devices':['cpu'],'sella':True}}
    d.manager.persist()
    # A reopened dialog has the configured environment but no in-memory readiness.
    assert not d.check_results
    d.structure=dict(name='Water',numbers=[8,1,1],positions=[[0,0,0],[.96,0,0],[-.24,.93,0]],charge=0,multiplicity=1)
    d.job.setCurrentIndex(d.job.findData('opt'));d.fields['steps'].setValue(17)
    d.environment_path.setText('unused unverified Python path')
    t.scenario(fail_check=outcome=='failed',slow_check=outcome=='cancelled')
    d.submit()
    assert d.setup_busy() and not d.queue_button.isEnabled()
    assert d.environment_path.text()==sys.executable
    with pytest.raises(ValueError,match='Wait'):d.submit()
    d.structure['positions'][1][0]=9.;d.fields['steps'].setValue(999)
    if outcome=='cancelled':d.stop_setup()
    t.wait(lambda:not d.setup_busy())
    if outcome=='ready':
        jobs=d.store.jobs();assert len(jobs)==1
        data=d.store.job(jobs[0]['id'])['input']
        assert data['kind']=='opt' and data['settings']['steps']==17
        assert data['structure']['positions'][1][0]==.96
        assert data['model']['sha256']=='a'*64
        assert t.calls()==['check'] and not t.installations
        assert d.tabs.currentIndex()==1
    else:
        assert not d.store.jobs() and not d.check_results
        assert ('Nothing queued' if outcome=='failed' else 'stopped') in d.readiness.text()
    assert d.queue_button.isEnabled()
