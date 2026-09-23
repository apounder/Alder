"""Native walkthrough checks in a separate Qt process; no model downloads."""
import time
from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QWizard
from molecule_studio import setup_ui as ui


@pytest.mark.parametrize('cuda,cancel', [(False, False), (True, False), (True, True)])
def test_walkthrough_detects_host_keeps_worker_alive_and_saves_device(tmp_path, monkeypatch, cuda, cancel):
    app = QApplication.instance() or QApplication([])
    info = dict(cpu='Test CPU', threads=8, gpus=[], error='')
    if cuda:
        info['gpus'] = [dict(name='Test NVIDIA GPU', memory_mb='8192', driver='610')]
    monkeypatch.setattr(ui, 'hardware', lambda: info)
    manager = SimpleNamespace(root=tmp_path, owns_queue=True, process=None, preparing=None, config={})
    started, release = Event(), Event()
    calls = []
    def run(root, names, device, **kwargs):
        calls.append((names, device, kwargs['token']))
        started.set()
        assert release.wait(10)
        if kwargs['cancelled']():
            return False
        from molecule_studio.mlip.environment import atomic_json
        atomic_json(root / 'environments.json', {'aimnet2': {'preferred_device': device}})
        kwargs['emit']('Calculation check passed')
        return True
    monkeypatch.setattr(ui, 'run_setup', run)
    wizard = ui.SetupWizard(manager=manager)
    wizard.show()
    try:
        assert len(wizard.pageIds()) == 3
        assert 'Test CPU' in wizard.hardware_label.text()
        assert wizard.page(0).title() == 'Choose models and hardware'
        wizard.next()
        assert wizard.currentId() == 1
        assert 'do not need a Hugging Face' in wizard.access_text.text()
        wizard.next()
        deadline = time.monotonic() + 10
        while not started.is_set() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert started.is_set()
        assert calls[0][1] == ('cuda' if cuda else 'cpu')
        assert manager.preparing == 'guided-setup'
        assert not wizard.progress_page.isComplete()
        assert not wizard.button(QWizard.WizardButton.FinishButton).isEnabled()
        assert not wizard.button(QWizard.WizardButton.BackButton).isVisible()
        wizard.accept()
        assert wizard.isVisible(), 'Finish must not destroy a running QThread'
        if cancel:
            wizard.reject()
            assert wizard.isVisible()
        release.set()
        while wizard.runner is not None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert wizard.runner is None
        assert manager.preparing is None
        assert wizard.success is not cancel
        assert wizard.button(QWizard.WizardButton.FinishButton).isEnabled()
        if not cancel:
            assert manager.config['aimnet2']['preferred_device'] == calls[0][1]
        wizard.accept()
        assert wizard.result() == QDialog.DialogCode.Accepted
    finally:
        release.set()
        if wizard.runner is not None:
            wizard.runner.wait(10000)
            app.processEvents()
        wizard.close()


def test_restricted_model_shows_early_access_and_masked_token(tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui, 'data_root', lambda: tmp_path)
    monkeypatch.setattr(ui, 'hardware', lambda: dict(cpu='CPU', threads=1, gpus=[]))
    wizard = ui.SetupWizard()
    wizard.show()
    for index in range(wizard.models.count()):
        item = wizard.models.item(index)
        item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) == 'uma-s-1p2' else Qt.CheckState.Unchecked)
    wizard.next()
    assert 'uma-s-1p2' in wizard.access_text.text()
    assert wizard.token.isVisible()
    assert wizard.token.echoMode() == QLineEdit.EchoMode.Password
    assert not wizard.accept_licence.isChecked()
    wizard.close()
    app.processEvents()
