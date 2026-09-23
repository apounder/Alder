"""Native installation and repair walkthrough using the shared setup engine."""
from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWizard, QWizardPage)
from .mlip.environment import choose_device, hardware, redact
from .mlip.registry import CATALOGUE
from .mlip.setup import (ACCESS_URL, TOKEN_URL, RECOMMENDED, data_root, licensed,
                         read_json, run_setup, setup_lock)


def label(text):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


class SetupRunner(QThread):
    message = Signal(str)

    def __init__(self, root, names, device, accepted, token, repair, in_app, parent):
        super().__init__(parent)
        self.root, self.names, self.device = root, names, device
        self.accepted, self.token, self.repair, self.in_app = accepted, token, repair, in_app
        self.success = False

    def run(self):
        try:
            with setup_lock(self.root, in_app=self.in_app):
                self.success = run_setup(self.root, self.names, self.device, accepted=self.accepted,
                    token=self.token, repair=self.repair, emit=self.message.emit,
                    cancelled=self.isInterruptionRequested)
        except Exception as error:
            self.message.emit(redact(error))
        finally:
            self.token = None


class InstallPage(QWizardPage):
    def isComplete(self):
        return self.wizard() is None or self.wizard().runner is None


class SetupWizard(QWizard):
    def __init__(self, parent=None, manager=None):
        super().__init__(parent)
        self.manager = manager
        self.root = manager.root if manager else data_root()
        self.state = read_json(self.root / 'setup-state.json')
        self.runner = None
        self.success = False
        self.setWindowTitle('Set up Molecule Studio')
        self.resize(760, 640)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        choices, layout = self.add_page('Choose models and hardware')
        layout.addWidget(label('Choose the models you want. Setup installs their dependencies and checks a real calculation. Leave all unchecked for the viewer only. Allow several GB per calculator.'))
        self.models = QListWidget()
        selected = self.state.get('selection', RECOMMENDED)
        for name, spec in CATALOGUE.items():
            access = 'Hugging Face access' if spec['backend'] == 'uma' else 'licence required' if licensed(name) else 'no account needed'
            item = QListWidgetItem(f'{name} — {access}')
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip(spec['domain'])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in selected else Qt.CheckState.Unchecked)
            self.models.addItem(item)
        layout.addWidget(self.models)
        all_models = QPushButton('Select all models')
        all_models.clicked.connect(lambda: [self.models.item(i).setCheckState(Qt.CheckState.Checked) for i in range(self.models.count())])
        layout.addWidget(all_models)
        self.device = QComboBox()
        for title, value in [('Automatic — detect this computer', 'auto'), ('Processor (CPU)', 'cpu'), ('NVIDIA graphics card (CUDA)', 'cuda')]:
            self.device.addItem(title, value)
        self.device.setCurrentIndex(self.device.findData(self.state.get('device', 'auto')))
        layout.addWidget(self.device)
        self.hardware_label = label('')
        layout.addWidget(self.hardware_label)
        recheck = QPushButton('Recheck hardware')
        recheck.clicked.connect(self.detect_hardware)
        layout.addWidget(recheck)
        self.repair = QCheckBox('Repair selected environments (keep downloaded weights and jobs)')
        layout.addWidget(self.repair)
        access_page, access_layout = self.add_page('Model access and licences')
        self.access_text = label('')
        access_layout.addWidget(self.access_text)
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText('Hugging Face read token — leave blank to reuse an existing login')
        self.token.setAccessibleName('Hugging Face read token')
        access_layout.addWidget(self.token)
        self.access_links = []
        for title, url, backend in [('Request UMA access', ACCESS_URL, 'uma'), ('Create a read token', TOKEN_URL, 'uma'),
                                    ('Read MACE-OFF23 licence', 'https://github.com/gabor1/ASL', 'mace')]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, address=url: QDesktopServices.openUrl(QUrl(address)))
            access_layout.addWidget(button)
            self.access_links.append((button, backend))
        self.accept_licence = QCheckBox('I have the required access and accept the terms shown for my selected restricted models.')
        access_layout.addWidget(self.accept_licence)
        access_layout.addWidget(label('Verified cached models work offline. Missing access leaves that model pending; other models can finish. GPU packages require internet unless already installed. Click Next to install and check your selections.'))
        self.progress_page, progress_layout = self.add_page('Install and verify', InstallPage)
        self.status = label('Preparing setup…')
        progress_layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2500)
        progress_layout.addWidget(self.log)
        self.currentIdChanged.connect(self.page_changed)
        self.models.itemChanged.connect(self.update_access)
        self.update_access()
        self.detect_hardware()

    def add_page(self, title, page_type=QWizardPage):
        page = page_type()
        page.setTitle(title)
        layout = QVBoxLayout(page)
        self.addPage(page)
        return page, layout

    def names(self):
        return [self.models.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.models.count())
                if self.models.item(i).checkState() == Qt.CheckState.Checked]

    def detect_hardware(self):
        self.info = hardware()
        lines = [f'Processor: {self.info["cpu"]} ({self.info["threads"]} logical cores)']
        lines += [f'{g["name"]}: {g["memory_mb"]} MB, driver {g["driver"]}' for g in self.info['gpus']]
        if self.info.get('error') or self.info.get('note'):
            lines.append(self.info.get('error') or self.info['note'])
        self.hardware_label.setText('\n'.join(lines))

    def update_access(self):
        restricted = [name for name in self.names() if licensed(name)]
        self.access_text.setText('\n\n'.join(f'{name}: {CATALOGUE[name]["license"]}' for name in restricted)
                                or 'Your public models do not need a Hugging Face account or token.')
        self.token.setVisible(any(CATALOGUE[n]['backend'] == 'uma' for n in self.names()))
        self.accept_licence.setVisible(bool(restricted))
        for button, backend in self.access_links:
            button.setVisible(any(CATALOGUE[n]['backend'] == backend for n in restricted))

    def validateCurrentPage(self):
        if self.currentId() == 0:
            try:
                self.resolved_device = choose_device(self.device.currentData(), self.info) if self.names() else 'cpu'
            except ValueError as error:
                QMessageBox.warning(self, 'Hardware needs attention', str(error))
                return False
        return super().validateCurrentPage()

    def page_changed(self, page):
        if page != 2 or self.runner is not None:
            return
        self.success = False
        if self.manager:
            if not self.manager.owns_queue or self.manager.process is not None or self.manager.preparing is not None:
                self.status.setText('Wait for the active calculation/setup to finish, and use the first open Studio window.')
                return
            self.manager.preparing = 'guided-setup'
        self.log.clear()
        self.status.setText('Installing and checking selected models. Cancel saves completed steps.')
        accepted = [n for n in self.names() if licensed(n)] if self.accept_licence.isChecked() else []
        self.runner = SetupRunner(self.root, self.names(), self.resolved_device, accepted,
                                  self.token.text().strip() or None, self.repair.isChecked(), bool(self.manager), self)
        self.token.clear()
        self.runner.message.connect(self.log.appendPlainText)
        self.runner.finished.connect(self.finished_setup)
        self.setOption(QWizard.WizardOption.NoBackButtonOnLastPage, True)
        self.progress_page.completeChanged.emit()
        self.button(QWizard.WizardButton.BackButton).setEnabled(False)
        self.button(QWizard.WizardButton.FinishButton).setEnabled(False)
        self.runner.start()

    def finished_setup(self):
        self.success = self.runner.success
        self.runner.deleteLater()
        self.runner = None
        self.setOption(QWizard.WizardOption.NoBackButtonOnLastPage, False)
        self.progress_page.completeChanged.emit()
        if self.manager:
            self.manager.config = read_json(self.root / 'environments.json')
            self.manager.preparing = None
        for button in (QWizard.WizardButton.BackButton, QWizard.WizardButton.CancelButton, QWizard.WizardButton.FinishButton):
            self.button(button).setEnabled(True)
        self.status.setText('Your selected models are ready. Click Finish to continue.' if self.success else
                            'Some steps need attention. Review the messages and go Back to retry. Completed work is saved.')

    def reject(self):
        if self.runner is not None:
            self.runner.requestInterruption()
            self.status.setText('Stopping after the current package operation. Completed steps will be kept.')
            self.button(QWizard.WizardButton.CancelButton).setEnabled(False)
        else:
            super().reject()

    def accept(self):
        # Qt may refresh Finish after currentIdChanged; never destroy a live worker.
        if self.runner is None:
            super().accept()

    def closeEvent(self, event):
        if self.runner is not None:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)


def standalone():
    from .ui import configure_app
    app = QApplication.instance() or QApplication([])
    configure_app(app)
    wizard = SetupWizard()
    result = wizard.exec()
    return 0 if result == QDialog.DialogCode.Accepted and wizard.success else 1
