"""Offline 2D drawing, representation switching, and background conversion."""
import base64
import json
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QUrl, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from .ui import label
from .structure import layout_2d, embed_3d


class SketchBridge(QObject):
    command = Signal(str)
    initialized = Signal()
    state = Signal(str)
    output = Signal(str, str)
    message = Signal(str, str)

    @Slot()
    def ready(self):
        self.initialized.emit()

    @Slot(str)
    def stateChanged(self, value):
        self.state.emit(value)

    @Slot(str, str)
    def result(self, purpose, value):
        self.output.emit(purpose, value)

    @Slot(str, str)
    def notice(self, value, kind):
        self.message.emit(value, kind)


class ConversionSignals(QObject):
    finished = Signal(str, object)
    failed = Signal(str)


class Conversion(QRunnable):
    def __init__(self, mode, data, name):
        super().__init__()
        self.mode, self.data, self.name = mode, data, name
        self.signals = ConversionSignals()

    def run(self):
        try:
            result = layout_2d(self.data) if self.mode == '2d' else embed_3d(self.data, self.name)
            self.signals.finished.emit(self.mode, result)
        except Exception as error:
            self.signals.failed.emit(str(error))


class SketchMixin:
    def install_sketch(self, assets, side):
        self.builder_mode = '3d'
        self.sketch_ready = False
        self.sketch_started = False
        self.sketch_dirty = False
        self.sketch_source_revision = -1
        self.sketch_pending = []
        self.converting = False
        self.sketch_export_path = None
        self.sketch_assets = assets
        self.builder_modebar = QWidget()
        row = QHBoxLayout(self.builder_modebar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.builder_modes = {}
        for mode in ('2d', '3d'):
            button = QPushButton(mode.upper())
            button.setCheckable(True)
            button.setObjectName('modeButton')
            button.clicked.connect(lambda checked=False, mode=mode: self.set_builder_mode(mode))
            row.addWidget(button)
            self.builder_modes[mode] = button
        self.viewbar.insertWidget(1, self.builder_modebar)
        self.builder_modebar.hide()
        self.builder_modes['3d'].setChecked(True)
        self.builder_convert = QPushButton('Convert to 3D')
        self.builder_convert.setObjectName('primary')
        self.builder_convert.clicked.connect(self.convert_sketch)
        self.viewbar.insertWidget(2, self.builder_convert)
        self.builder_convert.hide()
        self.builder_2d_panel = QWidget()
        panel = QVBoxLayout(self.builder_2d_panel)
        panel.setContentsMargins(0, 0, 0, 0)
        panel.setSpacing(14)
        panel.addWidget(label('2D structure editor', 'sectionTitle'))
        panel.addWidget(label('Draw your molecule', 'fileTitle'))
        panel.addWidget(label('Use the drawing toolbar for atoms, bonds, rings, charges, and stereochemistry. Double-click an atom or bond to edit its properties.', 'muted'))
        self.sketch_note = label('Your existing 3D geometry is preserved while you draw.', 'notice')
        panel.addWidget(self.sketch_note)
        convert = QPushButton('Convert sketch to 3D')
        convert.setObjectName('primary')
        convert.clicked.connect(self.convert_sketch)
        panel.addWidget(convert)
        self.sketch_convert_side = convert
        panel.addWidget(label('The conversion creates a local RDKit conformer and an undo checkpoint in the 3D editor.', 'muted'))
        row = QHBoxLayout()
        for title, cmd in (('Undo', 'undo'), ('Redo', 'redo'), ('Clean 2D', 'layout')):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, cmd=cmd: self.sketch_command(type=cmd))
            row.addWidget(button)
        panel.addLayout(row)
        panel.addWidget(label('Save your sketch', 'sectionTitle'))
        row = QHBoxLayout()
        for fmt in ('mol', 'png', 'svg'):
            button = QPushButton(fmt.upper())
            button.clicked.connect(lambda checked=False, fmt=fmt: self.export_sketch(fmt))
            row.addWidget(button)
        panel.addLayout(row)
        panel.addWidget(label('MOL retains the 2D drawing and stereochemistry. PNG/SVG export the line drawing. Switch to 3D to use Studio figure styling.', 'muted'))
        panel.addStretch()
        side.addWidget(self.builder_2d_panel)
        self.builder_2d_panel.hide()
        self.sketch_web = QWebEngineView()
        self.sketch_web.setMinimumHeight(360)
        self.sketch_web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.sketch_web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.sketch_bridge = SketchBridge(self)
        self.sketch_bridge.initialized.connect(self.sketch_initialized)
        self.sketch_bridge.state.connect(self.sketch_state_changed)
        self.sketch_bridge.output.connect(self.sketch_result)
        self.sketch_bridge.message.connect(self.sketch_message)
        self.sketch_channel = QWebChannel(self.sketch_web.page())
        self.sketch_channel.registerObject('sketch', self.sketch_bridge)
        self.sketch_web.page().setWebChannel(self.sketch_channel)
        self.sketch_web.page().profile().downloadRequested.connect(self.sketch_download)
        self.viewer_stack.addWidget(self.sketch_web)

    def sketch_download(self, download):
        if download.page() != self.sketch_web.page():
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Save 2D structure', download.downloadFileName())
        if path:
            download.setDownloadDirectory(str(Path(path).parent))
            download.setDownloadFileName(Path(path).name)
            download.accept()
        else:
            download.cancel()

    def ensure_sketch(self):
        if not self.sketch_started:
            self.sketch_started = True
            self.sketch_web.load(QUrl.fromLocalFile(str(self.sketch_assets / 'sketch.html')))

    def sketch_initialized(self):
        self.sketch_ready = True
        pending, self.sketch_pending = self.sketch_pending, []
        for payload in pending:
            self.sketch_command(**payload)
        self.update_builder_mode_ui()

    def sketch_command(self, **payload):
        if self.sketch_ready:
            self.sketch_bridge.command.emit(json.dumps(payload))
        else:
            self.sketch_pending.append(payload)

    def sketch_state_changed(self, text):
        self.sketch_state = json.loads(text)
        self.sketch_dirty = self.sketch_state.get('dirty', False)
        self.update_builder_mode_ui()

    def sketch_message(self, text, kind='info'):
        if kind == 'error':
            self.finish_conversion()
        self.sketch_note.setText(text)
        self.statusBar().showMessage(text)

    def set_builder_mode(self, mode):
        if self.converting:
            return
        self.builder_mode = mode
        if self.inspector.currentIndex() != self.build_tab:
            self.inspector.setCurrentIndex(self.build_tab)
        self.builder_active = self.builder_editing = True
        if mode == '2d':
            self.ensure_sketch()
            self.viewer_stack.setCurrentWidget(self.sketch_web)
            self.builder_command(type='visibility', visible=False)
            revision = self.builder_state.get('revision', 0)
            if not self.sketch_dirty and self.sketch_source_revision != revision:
                self.sketch_source_revision = revision
                self.run_conversion('2d', json.loads(json.dumps(self.builder_model)))
        else:
            self.viewer_stack.setCurrentWidget(self.builder_web)
            self.builder_command(type='visibility', visible=True)
        self.update_builder_mode_ui()

    def update_builder_mode_ui(self):
        if not hasattr(self, 'builder_modebar'):
            return
        active = self.inspector.currentIndex() == self.build_tab
        is2d = self.builder_mode == '2d'
        self.builder_modebar.setVisible(active)
        self.builder_convert.setVisible(active and (is2d or self.sketch_dirty))
        self.builder_convert.setEnabled(self.sketch_ready and not self.converting)
        self.sketch_convert_side.setEnabled(self.sketch_ready and not self.converting)
        self.builder_3d_panel.setVisible(not is2d)
        self.builder_2d_panel.setVisible(is2d)
        self.style.setVisible(not (active and is2d))
        self.fit_button.setVisible(not (active and is2d))
        self.view_options.setVisible(not (active and is2d))
        self.depth_cue.setVisible(not (active and is2d))
        for mode, button in self.builder_modes.items():
            button.setChecked(mode == self.builder_mode)
            button.setEnabled(not self.converting)
        if active:
            self.filename.setText('2D structure editor' if is2d else f"3D structure editor · {self.builder_model['name']}")
            self.export_button.setText('Export sketch' if is2d else 'Export figure')
            self.export_button.setEnabled((self.sketch_ready if is2d else bool(self.builder_model['atoms'])) and not self.converting)
        else:
            self.export_button.setText('Export figure')
        if not self.converting:
            self.sketch_note.setText('Unapplied 2D edits. Convert to 3D when ready; your previous 3D geometry is still available.' if self.sketch_dirty else 'Your existing 3D geometry is preserved. Edit this sketch, then convert it when ready.')
        if active and self.body.indexOf(self.inspector) != 1:
            self.body.insertWidget(1, self.inspector)
            self.body.setSizes([max(600, self.width()-460), 410])
        elif not active and self.body.indexOf(self.inspector) != 0:
            self.body.insertWidget(0, self.inspector)
            self.body.setSizes([340, max(600, self.width()-390)])

    def convert_sketch(self):
        if self.converting or not self.sketch_ready:
            return
        self.converting = True
        self.builder_command(type='locked', locked=True)
        self.sketch_command(type='lock', locked=True)
        self.update_builder_mode_ui()
        self.sketch_command(type='get', purpose='convert')

    def run_conversion(self, mode, data):
        self.converting = True
        self.builder_command(type='locked', locked=True)
        self.sketch_command(type='lock', locked=True)
        self.sketch_note.setText('Generating a 2D layout…' if mode == '2d' else 'Generating a 3D conformer locally…')
        self.update_builder_mode_ui()
        self.conversion_worker = Conversion(mode, data, self.builder_model.get('name', 'Built molecule'))
        self.conversion_worker.signals.finished.connect(self.conversion_finished)
        self.conversion_worker.signals.failed.connect(lambda error: self.sketch_message(error, 'error'))
        self.pool.start(self.conversion_worker)

    def finish_conversion(self):
        self.converting = False
        self.builder_command(type='locked', locked=False)
        self.sketch_command(type='lock', locked=False)
        self.update_builder_mode_ui()

    def conversion_finished(self, mode, result):
        self.finish_conversion()
        if mode == '2d':
            self.sketch_command(type='load', mol=result)
        else:
            model, note = result
            self.builder_command(type='restore', model=model)
            self.sketch_dirty = False
            self.sketch_command(type='saved')
            self.sketch_source_revision = self.builder_state.get('revision', 0) + 1
            self.set_builder_mode('3d')
            self.builder_message(note)

    def sketch_result(self, purpose, text):
        if purpose == 'convert':
            self.run_conversion('3d', text)
        elif self.sketch_export_path:
            try:
                if purpose == 'image':
                    self.sketch_export_path.write_bytes(base64.b64decode(text.split(',', 1)[1]))
                else:
                    self.sketch_export_path.write_text(text, encoding='utf-8')
                self.statusBar().showMessage(f'Saved {self.sketch_export_path.name}')
            except (OSError, ValueError) as error:
                self.sketch_message(str(error), 'error')
            self.sketch_export_path = None

    def export_sketch(self, fmt='png', path=None):
        if not self.sketch_ready or self.converting:
            return
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, 'Export 2D sketch', f'molecule-2d.{fmt}', f'{fmt.upper()} (*.{fmt})')
        if path:
            self.sketch_export_path = Path(path)
            if not self.sketch_export_path.suffix:
                self.sketch_export_path = self.sketch_export_path.with_suffix('.' + fmt)
            if fmt == 'mol':
                self.sketch_command(type='get', purpose='save')
            else:
                self.sketch_command(type='image', format=fmt)
