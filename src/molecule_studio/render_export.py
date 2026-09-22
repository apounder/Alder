"""Native progress and atomic movie downloads for the shared offline renderer."""
import base64
import os
from pathlib import Path
import tempfile

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog


class ExportBridge(QObject):
    progress = Signal(int, str)
    export_finished = Signal(str)

    @Slot(str)
    def fogChanged(self, state):
        self.parent().fog_changed(state)

    @Slot(int, str)
    def exportProgress(self, value, message):
        self.progress.emit(value, message)

    @Slot(str, float, result=bool)
    def videoChunk(self, text, position):
        return self.parent().save_video_chunk(text, position)

    @Slot(str)
    def exportFinished(self, status):
        self.export_finished.emit(status)


class ExportMixin:
    def connect_export_bridge(self, bridge):
        bridge.progress.connect(self.export_progress)
        bridge.export_finished.connect(self.finish_export)

    def begin_export_progress(self):
        self.export_dialog = QProgressDialog("Preparing export…", "Cancel", 0, 1000, self)
        dialog = self.export_dialog
        self.export_dialog.setWindowTitle("Rendering export")
        self.export_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.export_dialog.setAutoClose(False)
        self.export_dialog.setAutoReset(False)
        # Qt can deliver a closing dialog's queued signal after the next export
        # has started. Only the current dialog may cancel the current job.
        self.export_dialog.canceled.connect(lambda: self.send(type="exportCancel")
                                            if self.export_dialog is dialog and self.exporting else None)
        self.export_dialog.setValue(0)
        self.export_dialog.show()

    def export_progress(self, value, message):
        dialog = getattr(self, "export_dialog", None)
        if dialog:
            dialog.setLabelText(message)
            dialog.setValue(min(999, value))

    def end_export_progress(self):
        dialog = getattr(self, "export_dialog", None)
        if dialog:
            self.export_dialog = None
            # QProgressDialog.close() emits canceled even after a successful
            # export. A delayed WebChannel cancel can otherwise kill the next job.
            dialog.blockSignals(True)
            dialog.close()
            dialog.deleteLater()
        pending = getattr(self, "video_file", None)
        if pending:
            pending.close()
            Path(pending.name).unlink(missing_ok=True)
            self.video_file = None

    def save_video_chunk(self, text, position):
        pending = getattr(self, "video_file", None)
        if pending:
            try:
                if not float(position).is_integer() or position < 0:
                    return False
                pending.seek(int(position))
                pending.write(base64.b64decode(text, validate=True))
                return True
            except (OSError, ValueError) as error:
                self.statusBar().showMessage(str(error))
        return False

    def finish_export(self, status):
        pending = getattr(self, "video_file", None)
        if status == "complete" and pending:
            try:
                pending.close()
                os.replace(pending.name, self.video_path)
                self.statusBar().showMessage(f"Saved {self.video_path.name}")
                self.video_file = None
            except OSError as error:
                QMessageBox.warning(self, "Video export failed", str(error))
        elif status == "cancelled":
            self.statusBar().showMessage("Export cancelled; existing files were kept.")
        self.end_export_progress()
        self.image_path = None
        self.exporting = False
        self.export_button.setEnabled(True)

    def export_video(self):
        if self.exporting:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export animation", "molecule.webm", "WebM video (*.webm)")
        if path:
            self.render_video(Path(path).with_suffix(".webm"))

    def render_video(self, path):
        if self.exporting or self.busy or not self.renderer_ready:
            return
        calc = self.calculation
        if calc is None or self.builder_active or self.comparison_active:
            QMessageBox.information(self, "Choose a calculation", "Open a calculation and switch to its Calculation view to export a trajectory or vibrational mode.")
            return
        try:
            kind = self.video_source.currentData()
            fps = self.video_fps.value()
            if kind == "vibration":
                mode = self.vibration_table.currentRow()
                if calc.displacements is None or not 0 <= mode < len(calc.displacements):
                    raise ValueError("Select a mode with displacement vectors in Results → Vibrations first.")
                base = calc.vibration_coords.copy() if calc.vibration_coords is not None else calc.coords[-1].copy()
                vectors = calc.displacements[mode].copy()
                if self.display_coords is not None:
                    source, target = calc.coords[-1], self.display_coords[-1]
                    u, _, vt = np.linalg.svd((source-source.mean(axis=0)).T @ (target-target.mean(axis=0)))
                    rotation = u @ np.diag([1, 1, np.linalg.det(u@vt)]) @ vt
                    base = (base-source.mean(axis=0)) @ rotation + target.mean(axis=0)
                    vectors = vectors @ rotation
                maximum = np.linalg.norm(vectors, axis=1).max()
                if maximum <= 1e-12:
                    raise ValueError("This mode has no usable displacement vectors.")
                period = self.video_period.value()
                video = dict(kind=kind, fps=fps, count=period*self.video_cycles.value(), framesPerCycle=period,
                             base=base.tolist(), vectors=(vectors/maximum).tolist(), amplitude=self.vib_amplitude.value()/100)
            else:
                points = self.display_coords if self.display_coords is not None else calc.coords
                if kind == "path":
                    reaction_path = calc.reaction_path
                    if reaction_path is None or np.any(reaction_path.steps < 0):
                        raise ValueError("All IRC/scan points need linked geometries. For ORCA IRC, attach its full trajectory XYZ first.")
                    points = points[reaction_path.steps]
                hold = self.video_hold.value()
                video = dict(kind=kind, fps=fps, count=len(points)*hold, frames=points.tolist(), hold=hold)
            if video["count"] > 12000:
                raise ValueError("The video exceeds 12,000 frames. Reduce frames per geometry or the number of vibration cycles.")
            self.play.setChecked(False)
            self.vib_play.setChecked(False)
            self.surface_timer.stop()
            ratio = self.web.width()/max(1, self.web.height())
            edge = self.video_size.currentData()
            width, height = (edge, round(edge/ratio)) if ratio >= 1 else (round(edge*ratio), edge)
            width, height = max(2, width//2*2), max(2, height//2*2)
            self.video_path = Path(path)
            self.video_file = tempfile.NamedTemporaryFile(prefix=".molecule-studio-", suffix=".webm", dir=self.video_path.parent, delete=False)
            self.exporting = True
            self.export_button.setEnabled(False)
            self.begin_export_progress()
            self.send(type="export", width=width, height=height, engine=self.export_engine.currentData(),
                      raySamples=self.ray_samples.value(), samples=1, transparent=False, video=video)
        except (OSError, ValueError) as error:
            self.end_export_progress()
            self.exporting = False
            self.export_button.setEnabled(True)
            QMessageBox.warning(self, "Cannot export animation", str(error))
