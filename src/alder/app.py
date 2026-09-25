"""Desktop interface; files and rendering stay on this machine."""

import base64
import csv
import json
from io import BytesIO
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image
from matplotlib.ticker import MaxNLocator
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot, QEvent
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QMainWindow, QMessageBox, QTableWidgetItem,
)

from .data import Calculation, read_calculation, read_cube, register_cube, validate_mapping
from .ui import build_ui, configure_app, MODES
from .builder import BuilderMixin
from .results import ResultsMixin
from .paths import attach_irc_trajectory
from .render_export import ExportMixin, ExportBridge
from .data import check_file
from .trajectory import read_trajectory
from .comparison import ComparisonMixin

ASSETS = Path(__file__).parent / "assets"
UNITS = {"kcal/mol": 627.509474, "kJ/mol": 2625.499639, "Eh": 1.0}


class Bridge(ExportBridge):
    command = Signal(str)
    initialized = Signal()
    error = Signal(str)
    image = Signal(str)
    copied = Signal(str)

    @Slot(str)
    def copyReady(self, model):
        self.copied.emit(model)

    @Slot()
    def ready(self):
        self.initialized.emit()

    @Slot(str)
    def reportError(self, message):
        self.error.emit(message)

    @Slot(str)
    def imageReady(self, data):
        self.image.emit(data)


class LoadSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class LoadFile(QRunnable):
    def __init__(self, path, calculation, trajectory=False, compare=False):
        super().__init__()
        self.path, self.calculation = path, calculation
        self.trajectory = trajectory
        self.compare = compare
        self.signals = LoadSignals()

    def run(self):
        try:
            if self.trajectory:
                result = ('attached', attach_irc_trajectory(self.calculation, check_file(self.path)), None)
            elif self.path.suffix.lower() in {".cube", ".cub"}:
                cube = read_cube(self.path)
                registration = register_cube(self.calculation, cube) if self.calculation else None
                result = ("cube", cube, registration)
            elif self.path.suffix.lower() in {'.xyz', '.extxyz', '.traj'}:
                data = read_trajectory(self.path)
                result = ('calculation', data, None)
            elif self.path.suffix.lower() in {".mol", ".sdf", ".pdb"}:
                if self.path.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError("Structure files are limited to 20 MB.")
                result = ("structure", (self.path.name, self.path.read_text(encoding="utf-8")), None)
            else:
                result = ("calculation", read_calculation(self.path), None)
            self.signals.finished.emit(result)
        except Exception as error:
            self.signals.failed.emit(str(error) or type(error).__name__)


class Window(ComparisonMixin, ExportMixin, ResultsMixin, BuilderMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Alder")
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1420, screen.width() - 40), min(960, screen.height() - 60))
        self.setMinimumSize(1060, 740)
        self.calculation = None
        self.cube = None
        self.cubes = []
        self.cube_step = None
        self.display_coords = None
        self.step = 0
        self._plot_owner = None
        self._plot_options = None
        self._playback_fraction = 0.0
        self.vibration_preview = False
        self.init_builder()
        self.measurement_states = {}
        self.renderer_ready = False
        self.busy = False
        self.pending_files = []
        self.load_as_comparison = False
        self.image_path = None
        self.image_dpi = 300
        self.exporting = False
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.advance)
        self.surface_timer = QTimer(self)
        self.surface_timer.setSingleShot(True)
        self.surface_timer.setInterval(180)
        self.surface_timer.timeout.connect(self.refresh_surface)
        self.setAcceptDrops(True)
        self.build_ui()
        from .mlip_ui import JobManager
        self.mlip_manager = JobManager(self)
        self.statusBar().showMessage("Ready · Files stay on this machine")

    def build_ui(self):
        build_ui(self, ASSETS, Bridge, UNITS)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.Drop) and event.mimeData().hasUrls():
            paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
            if paths:
                event.acceptProposedAction()
                if event.type() == QEvent.Type.Drop:
                    self.open_paths(paths)
                return True
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event):
        self.eventFilter(self, event)

    def dropEvent(self, event):
        self.eventFilter(self, event)

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Open calculation, cube, or structure", "",
            "Molecular files (*.log *.out *.cube *.cub *.xyz *.extxyz *.traj *.mol *.sdf *.pdb);;All files (*)")
        self.open_paths([Path(p) for p in paths])

    def open_paths(self, paths, compare=False):
        if self.busy:
            self.statusBar().showMessage("A file is still loading. Please wait before opening another.")
            return
        structures = [p for p in paths if p.suffix.lower() in {".mol", ".sdf", ".pdb"}]
        if structures and len(paths) > 1:
            QMessageBox.information(self, "Open structure", "Import one structure at a time. Calculation and cube files can be opened together separately.")
            return
        outputs = [p for p in paths if p.suffix.lower() not in {".cube", ".cub"}]
        cubes = [p for p in paths if p.suffix.lower() in {".cube", ".cub"}]
        if len(cubes) + (0 if outputs else len(self.cubes)) > 8 or (len(outputs) > 1 and cubes):
            QMessageBox.information(self, "Open files", "Open multiple outputs together, or one calculation with up to eight cube fields. Load cubes for the active calculation separately when comparing outputs.")
            return
        self.load_as_comparison = compare or len(outputs) > 1
        self.pending_files = outputs + cubes
        self.load_next()

    def load_next(self):
        if not self.pending_files:
            self.busy = False
            self.open_button.setEnabled(True)
            self.calculation_picker.setEnabled(True)
            if self.load_as_comparison:
                self.load_as_comparison = False
                self.inspector.setCurrentIndex(self.compare_tab)
                self.show_comparison()
            return
        path = self.pending_files.pop(0)
        self.busy = True
        self.open_button.setEnabled(False)
        self.calculation_picker.setEnabled(False)
        self.play.setChecked(False)
        self.statusBar().showMessage(f"Reading {path.name}…")
        self.worker = LoadFile(path, self.calculation, compare=self.load_as_comparison or
                               any(p.suffix.lower() in {'.cub','.cube'} for p in self.pending_files))
        self.worker.signals.finished.connect(self.loaded)
        self.worker.signals.failed.connect(self.load_failed)
        self.pool.start(self.worker)

    def attach_trajectory(self, path):
        if self.busy or self.calculation is None:
            return
        self.busy = True
        self.open_button.setEnabled(False)
        self.play.setChecked(False)
        self.statusBar().showMessage('Reading IRC trajectory…')
        self.worker = LoadFile(Path(path), self.calculation, trajectory=True)
        self.worker.signals.finished.connect(self.loaded)
        self.worker.signals.failed.connect(self.load_failed)
        self.pool.start(self.worker)

    def loaded(self, result):
        kind, data, registration = result
        if kind == "structure":
            name, text = data
            if Path(name).suffix.lower() in {'.mol', '.sdf'} and (self.builder_mode == '2d' or '2D' in (text.splitlines()[1:2] or [''])[0]):
                self.ensure_sketch()
                self.builder_mode = '2d'
                self.sketch_dirty = True
                self.inspector.setCurrentIndex(self.build_tab)
                self.set_builder_mode('2d')
                self.sketch_command(type='load', mol=text.split('$$$$')[0], dirty=True)
                self.load_next()
                return
            self.inspector.setCurrentIndex(self.build_tab)
            self.set_builder_mode('3d')
            self.builder_command(type="load", name=name, text=text)
            self.load_next()
            return
        if kind in {"calculation", "attached"}:
            self.add_document(data, replace=kind == 'attached')
            self.activate_calculation(data)
        else:
            if registration is None:
                self.calculation = Calculation(data.name, data.atomnos, data.coords[None], np.array([np.nan]))
                self.add_document(self.calculation)
                self.filename.setText(data.name)
                self.details.setText("Cube surface\nNo calculation output loaded.")
                self.warning.setText("")
                self.warning.hide()
                self.slider.setRange(0, 0)
                self.play.setEnabled(False)
                self.update_energy_view()
                self.refresh_results()
                registration = (0, self.calculation.coords, 0.0)
            self.cubes.append((data, registration))
            index = len(self.cubes) - 1
            for control in (self.surface_field, self.color_field):
                control.blockSignals(True)
                control.addItem(data.name, index)
                control.setItemData(control.count() - 1, data.name, Qt.ItemDataRole.ToolTipRole)
                control.blockSignals(False)
            if index == 0:
                name = data.name.lower()
                mode = ("esp_vdw" if any(x in name for x in ("esp", "mep", "potential")) else
                        "nci" if "rdg" in name else "igm" if any(x in name for x in ("igm", "dg_inter", "dg_intra")) else
                        "density" if any(x in name for x in ("density", "dens", "rho")) else "orbital")
                self.surface_mode.setCurrentIndex(self.surface_mode.findData(mode))
                self.surface_field.setCurrentIndex(1)
            else:
                # Roles stay explicit in the inspector. A second field defaults
                # to coloring; choosing either dropdown can swap those roles.
                mode = self.surface_mode.currentData()
                if mode == "density" and any(x in data.name.lower() for x in ("esp", "mep", "potential")):
                    self.surface_mode.setCurrentIndex(self.surface_mode.findData("esp"))
                elif mode in {"density", "orbital"}:
                    self.surface_mode.setCurrentIndex(self.surface_mode.findData("custom"))
                self.color_field.setCurrentIndex(index + 1)
            self.inspector.setCurrentIndex(1)
        self.export_button.setEnabled(self.renderer_ready)
        self.statusBar().showMessage(f"Loaded {data.name}")
        self.load_next()
        self.builder_state_changed(json.dumps(self.builder_state))

    def activate_calculation(self, data, step=None):
        self.play.setChecked(False)
        self.stop_vibration(restore=False)
        self.inspector.setCurrentIndex(0)
        self.studio_tab_changed(0)
        self.clear_cube()
        self.calculation = data
        self.step = len(data.coords)-1 if step is None else min(step, len(data.coords)-1)
        self.display_coords = None
        self.filename.setText(data.name)
        self.details.setText('\n'.join(f'{k}: {v}' for k, v in data.summary.items()))
        self.warning.setText('\n'.join(data.warnings))
        self.warning.setVisible(bool(data.warnings))
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(data.coords)-1)
        self.slider.setValue(self.step)
        self.slider.blockSignals(False)
        self.play.setEnabled(len(data.coords)>1)
        self.update_energy_view()
        self.select_step(self.step, fit=True)
        self.refresh_results()
        if data.transitions is not None:
            self.results.setCurrentIndex(self.uv_tab)
        elif data.reaction_path is not None:
            self.results.setCurrentIndex(self.path_tab)
        self.calculation_picker.blockSignals(True)
        self.calculation_picker.setCurrentIndex(next((i for i,d in enumerate(self.documents) if d['calculation'] is data), -1))
        self.calculation_picker.blockSignals(False)
        self.export_button.setEnabled(self.renderer_ready)

    def load_failed(self, message):
        self.pending_files.clear()
        self.busy = False
        self.open_button.setEnabled(True)
        self.calculation_picker.setEnabled(True)
        self.load_as_comparison = False
        self.statusBar().showMessage("File could not be loaded; the previous view is retained.")
        QMessageBox.warning(self, "Could not open file", message)

    def clear_cube(self):
        self.cubes.clear()
        self.sent_fields = None
        self.cube = None
        self.cube_step = None
        self.display_coords = None
        self.surface_controls.setEnabled(False)
        for control, text in ((self.surface_field, "Drop or open a cube…"),
                              (self.color_field, "None · uniform color")):
            control.blockSignals(True)
            control.clear()
            control.addItem(text, None)
            control.blockSignals(False)
        self.cube_label.setText("Drop your cube files together, then choose their roles above.")
        self.surface_message.hide()
        self.send(type="cube", text=None)
        if self.calculation:
            self.select_step(self.step)

    def choose_measurement(self, enabled=True):
        if self.depth_cue.isChecked():
            self.depth_cue.setChecked(False)
            self.send(type='fogPick', enabled=False)
        self.send(type='measure', count=self.measurement_kind.currentData() if enabled else 0)

    def measurement_changed(self, bridge, text):
        self.measurement_states[bridge] = json.loads(text)
        self.update_measurement_ui()

    def update_measurement_ui(self):
        if not hasattr(self, 'measure_button'):
            return
        bridge = self.builder_bridge if self.builder_active else self.bridge
        state = self.measurement_states.get(bridge, {})
        count = state.get('count', 0)
        visible = not (self.builder_active and self.builder_editing and getattr(self, 'builder_mode', '3d') == '2d')
        self.measure_button.setVisible(visible)
        self.measure_button.setChecked(bool(count))
        self.measurement_panel.setVisible(visible and bool(count))
        if count:
            self.measurement_kind.blockSignals(True)
            self.measurement_kind.setCurrentIndex(self.measurement_kind.findData(count))
            self.measurement_kind.blockSignals(False)
        atoms = state.get('atoms', [])
        result = state.get('text', '')
        kind = 'Bond length' if state.get('kind') == 'Distance' else state.get('kind', '')
        self.measurement_readout.setText((' → '.join(atoms) + '\n' if atoms else '') +
                                        (f'{kind} · {result}' if result else f'Pick {count or 2} atoms in order ({len(atoms)}/{count or 2}).'))

    def send(self, **payload):
        kind = payload.get("type")
        if kind in {"style", "appearance", "fog", "figureAddons"} and hasattr(self, "builder_bridge"):
            self.builder_command(**payload)
        if kind in {"fit", "annotation", "fogPick", "measure", "exportCancel"} and self.builder_active:
            self.builder_command(**payload)
            return
        if kind == "export" and self.builder_active:
            self.builder_command(**{**payload, "type": "figure"})
            return
        if kind == "geometry" and self.builder_active and not payload.get("draft"):
            return
        if kind in {"cube", "surface"} and self.builder_active:
            payload["visible"] = False
        if self.renderer_ready:
            self.bridge.command.emit(json.dumps(payload, allow_nan=False))

    def renderer_initialized(self):
        self.renderer_ready = True
        if self.web.focusProxy():
            self.web.focusProxy().setAcceptDrops(True)
            self.web.focusProxy().installEventFilter(self)
        self.send(type="style", style=self.style.currentText())
        self.send(type="fog", **self.fog_options())
        self.appearance_changed()
        self.figure_addons_changed()
        if self.cube:
            self.refresh_surface(reload=True)
        if self.calculation:
            self.select_step(self.step, fit=True)
            if self.results.currentIndex()==self.vibration_tab:
                self.select_vibration(self.vibration_table.currentRow())
            self.export_button.setEnabled(True)
        if hasattr(self, "builder_bridge"):
            self.builder_state_changed(json.dumps(self.builder_state))
        if self.comparison_active:
            self.refresh_comparison(fit=True)

    def render_error(self, message):
        self.statusBar().showMessage("3D rendering error: " + message)
        self.end_export_progress()
        if self.exporting:
            self.exporting = False
            self.image_path = None
            self.export_button.setEnabled(True)
            QMessageBox.warning(self, "Figure export failed", message)

    def surface_options(self):
        return {"isoval": self.isovalue.value(), "opacity": self.opacity.value() / 100,
                "signed": self.signed_surface.isChecked(), "mode": self.surface_mode.currentData(),
                "min": self.color_min.value(), "max": self.color_max.value(),
                "fieldMin": self.cube.minimum if self.cube else 0,
                "fieldMax": self.cube.maximum if self.cube else 0,
                "scale": self.color_scale.currentData(), "gradient": self.gradient.currentData(),
                "legend": self.show_legend.isChecked()}

    def mode_changed(self, *_):
        mode = self.surface_mode.currentData()
        mapped = mode in {"esp", "esp_vdw", "nci", "igm", "custom"}
        self.surface_help.setText(MODES[mode][1])
        self.isovalue.setValue(MODES[mode][2])
        self.signed_surface.setChecked(mode == "orbital")
        self.signed_surface.setEnabled(mode == "orbital")
        self.isovalue.setEnabled(mode != "esp_vdw")
        self.gradient.setCurrentIndex(1 if mode in {"nci", "igm"} else 0)
        self.color_min.setValue(-0.05)
        self.color_max.setValue(0.05)
        self.color_scale.setCurrentIndex(0)
        for control in (self.color_min, self.color_max, self.color_scale, self.gradient, self.show_legend):
            self.surface_form.setRowVisible(control, mapped)
        self.surface_form.setRowVisible(self.color_scale, mode in {"nci", "igm", "custom"})
        self.surface_form.setRowVisible(self.signed_surface, mode == "orbital")
        self.color_field.setEnabled(mapped and mode != "esp_vdw")
        self.field_changed()

    def field_changed(self, *_):
        self.stop_vibration()
        index = self.surface_field.currentData()
        if index is None:
            self.cube = None
            self.cube_step = None
            self.display_coords = None
            self.send(type="cube", text=None)
            self.surface_controls.setEnabled(False)
            if self.calculation:
                self.select_step(self.step)
            return
        changed = self.cube is not self.cubes[index][0]
        self.cube, registration = self.cubes[index]
        self.cube_step, self.display_coords, rmsd = registration
        self.surface_controls.setEnabled(True)
        self.surface_visible.setChecked(True)
        self.cube_label.setText(f"Geometry {self.cube_step + 1} · RMSD {rmsd:.4f} Å\nField range {self.cube.minimum:.4g} to {self.cube.maximum:.4g}")
        self.slider.setValue(self.cube_step)
        self.select_step(self.cube_step, fit=changed)
        self.refresh_surface(reload=True)

    def selected_mapping(self):
        mode = self.surface_mode.currentData()
        if mode == "esp_vdw":
            return self.cube
        index = self.color_field.currentData()
        return self.cubes[index][0] if index is not None and mode not in {"orbital", "density"} else None

    def surface_is_visible(self):
        if self.vibration_preview or not self.cube or self.step != self.cube_step or not self.surface_visible.isChecked():
            return False
        return self.surface_has_contour()

    def surface_has_contour(self):
        if not self.cube:
            return False
        if self.surface_mode.currentData() == "esp_vdw":
            return True
        iso, lo, hi = self.isovalue.value(), self.cube.minimum, self.cube.maximum
        return lo < iso < hi or (self.surface_mode.currentData() == "orbital" and self.signed_surface.isChecked() and lo < -iso < hi)

    def schedule_surface(self, *_):
        self.surface_timer.start()

    def refresh_surface(self, reload=False):
        if not self.cube:
            return
        mode = self.surface_mode.currentData()
        mapped = mode in {"esp", "esp_vdw", "nci", "igm", "custom"}
        color = self.selected_mapping()
        message = ""
        try:
            if mapped and color is None:
                raise ValueError("Choose a color field to complete this mapped surface.")
            if mapped:
                validate_mapping(self.cube, color)
                if self.color_min.value() >= self.color_max.value():
                    raise ValueError("Color minimum must be smaller than color maximum.")
            if not self.surface_has_contour():
                message = "The isovalue lies outside this field's range; no surface will be visible."
        except ValueError as error:
            self.surface_message.setText(str(error))
            self.surface_message.show()
            self.send(type="cube", text=None)
            self.sent_fields = None
            return
        self.surface_message.setText(message)
        self.surface_message.setVisible(bool(message))
        # Sending fields only when they change keeps isovalue/opacity edits light.
        fields = (id(self.cube), id(color))
        if reload or getattr(self, "sent_fields", None) != fields:
            self.send(type="cube", text=self.cube.text, mapping=color.text if color else None,
                      options=self.surface_options(), visible=self.surface_is_visible())
            self.sent_fields = fields
        else:
            self.send(type="surface", options=self.surface_options(), visible=self.surface_is_visible())

    def appearance_changed(self, *_):
        preset = self.preset.currentText()
        if preset != getattr(self, "last_preset", None):
            self.last_preset = preset
            for control, value in ((self.outlines, preset not in {"Soft studio", "Tube", "Wire", "vdW"}),
                                   (self.ambient_occlusion, preset == "Soft studio"),
                                   (self.orthographic, preset != "Paton-inspired")):
                control.blockSignals(True)
                control.setChecked(value)
                control.blockSignals(False)
            self.style.setCurrentText({"Tube": "Stick", "Wire": "Stick", "vdW": "Space filling"}.get(preset, "Ball and stick"))
        self.preset_note.setText("Based on Robert Paton's published styling: thin black bonds, pale carbon, smaller hydrogen spheres. WebGL approximation of the PyMOL look."
                                if preset == "Paton-inspired" else "Clean molecular graphics with adjustable outlines, depth shading, and projection.")
        if preset in {"Flat", "Tube", "Ball and tube", "Wire", "vdW"}:
            self.preset_note.setText("Inspired by xyzrender: " + {
                "Flat": "unshaded colors and fine outlines.", "Tube": "thick element-colored sticks.",
                "Ball and tube": "rounded atoms and element-colored bonds.",
                "Wire": "thin element-colored sticks.", "vdW": "space-filling van der Waals spheres.",
            }[preset])
        self.send(type="appearance", preset=preset, outline=self.outlines.isChecked(),
                  ao=self.ambient_occlusion.isChecked(), orthographic=self.orthographic.isChecked())

    def figure_addon_options(self):
        return dict(nci=self.auto_contacts.isChecked(), vdw=self.vdw_overlay.isChecked(),
                    opacity=self.vdw_opacity.value()/100)

    def figure_addons_changed(self, *_):
        self.vdw_opacity.setEnabled(self.vdw_overlay.isChecked())
        self.send(type="figureAddons", **self.figure_addon_options())

    def select_step(self, step, fit=False):
        self.stop_vibration(restore=False)
        if not self.calculation:
            return
        self.step = step
        self.step_label.setText(f"Geometry {step + 1} / {len(self.calculation.coords)}" +
                               (" · surface hidden at this step" if self.cube and step != self.cube_step else ""))
        if not self.comparison_active:
            self.send(type="geometry", xyz=self.calculation.xyz(step, self.display_coords), annotationKey=str(id(self.calculation)),
                      fit=fit, surface=self.surface_is_visible())
        for i, entry in enumerate(self.documents):
            if entry['calculation'] is self.calculation:
                entry['step'] = step
                control = self.compare_table.cellWidget(i, 1)
                control.blockSignals(True)
                control.setValue(step+1)
                control.blockSignals(False)
        energy = self.calculation.energies[step]
        self.energy_label.setText(f"{energy:.10f} Eh" if np.isfinite(energy) else "Energy unavailable")
        relative = self.plot_values()[step]
        self.relative_label.setText(f"{relative:+.5f} {self.units.currentText()} · {self.reference.currentText().lower()}"
                                    if np.isfinite(relative) else "No saved energy for this geometry")
        checks = self.calculation.convergence.get(step, [])
        self.convergence_label.setText("\n".join(
            f"{name}: {value:.3g} / {target:.3g} {'✓' if abs(value) <= target else '·'}"
            for name, value, target in checks if np.isfinite(value)))
        forces = self.calculation.metadata.get('max_forces', [])
        if len(forces) > step and np.isfinite(forces[step]):
            self.convergence_label.setText(f'Maximum force: {forces[step]:.6f} eV/Å (saved)')
        self.table.selectRow(step)
        if hasattr(self, 'path_panel'):
            self.path_panel.select_step(step)
        self.update_plot_selection()

    def plot_values(self):
        if not self.calculation:
            return np.array([])
        options = (self.reference.currentIndex(), self.units.currentText())
        if self._plot_owner is self.calculation and self._plot_options == options:
            return self._plot_values
        values = self.calculation.energies.copy()
        finite = values[np.isfinite(values)]
        if len(finite):
            if options[0] == 0:
                values -= np.min(finite)
            elif options[0] == 1:
                values -= finite[0]
        self._plot_values = values * UNITS[options[1]]
        self._plot_owner, self._plot_options = self.calculation, options
        return self._plot_values

    def update_energy_view(self, *_):
        if not self.calculation:
            return
        values = self.plot_values()
        self.table.setRowCount(len(values))
        title = self.calculation.metadata.get('energy_label', 'SCF / DFT energy')
        self.energy_profile_title.setText(title)
        self.table.setHorizontalHeaderLabels(["Geometry", f"{title} (Eh)", f"{self.reference.currentText()} ({self.units.currentText()})"])
        for row, (energy, relative) in enumerate(zip(self.calculation.energies, values)):
            for col, value in enumerate((str(row + 1), f"{energy:.10f}" if np.isfinite(energy) else "—",
                                         f"{relative:.6f}" if np.isfinite(relative) else "—")):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.select_step(min(self.step, len(values) - 1))
        self.draw_plot()

    def draw_plot(self):
        self.ax.clear()
        self.ax.spines[["top", "right"]].set_visible(False)
        self.ax.spines[["bottom", "left"]].set_color("#cfdae0")
        self.ax.tick_params(colors="#627986", labelsize=9)
        self.ax.grid(axis="y", color="#e9eff2")
        self.ax.set_xlabel("Geometry step", color="#627986", fontsize=9)
        self.ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        self.ax.set_ylabel(f"{'E' if self.reference.currentIndex() == 2 else 'ΔE'} ({self.units.currentText()})", color="#627986", fontsize=9)
        values = self.plot_values()
        self._plot_cursor = self._plot_marker = None
        if len(values) and np.isfinite(values).any():
            self.ax.plot(np.arange(1, len(values) + 1), values, "o-", color="#178b91", markersize=4, linewidth=1.5)
            self._plot_cursor = self.ax.axvline(self.step + 1, color="#9ab4bd", linewidth=1)
            self._plot_marker, = self.ax.plot([], [], "o", color="#dd7754", markersize=8)
            self.update_plot_selection()
        else:
            self.ax.text(0.5, 0.5, "An energy profile will appear here", ha="center", va="center",
                         transform=self.ax.transAxes, color="#83949d")
        self.canvas.draw_idle()

    def update_plot_selection(self):
        if self._plot_cursor is None or not self.calculation:
            return
        x = self.step + 1
        self._plot_cursor.set_xdata([x, x])
        value = self.plot_values()[self.step]
        if np.isfinite(value):
            self._plot_marker.set_data([x], [value])
        else:
            self._plot_marker.set_data([], [])
        if self.results.isVisible() and self.results.currentIndex() == 0:
            self.canvas.draw_idle()

    def plot_clicked(self, event):
        if self.calculation and event.inaxes == self.ax and event.xdata is not None:
            self.slider.setValue(max(0, min(len(self.calculation.coords) - 1, round(event.xdata) - 1)))

    def toggle_play(self, checked):
        if checked:
            self.stop_vibration()
            self._playback_time = time.monotonic()
            self._playback_fraction = 0.0
        self.play.setText("Pause" if checked else "Play")
        self.timer.start() if checked else self.timer.stop()

    def advance(self):
        if self.calculation:
            frames = 1
            if self.timer.isActive():
                now = time.monotonic()
                self._playback_fraction += (now - self._playback_time) * self.trajectory_speed.value() / 0.350
                self._playback_time = now
                frames = max(1, int(self._playback_fraction))
                self._playback_fraction = max(0, self._playback_fraction - frames)
            path = self.calculation.reaction_path
            if path is not None and self.results.currentIndex() == self.path_tab:
                steps = path.steps[path.steps >= 0]
                if len(steps):
                    current = np.flatnonzero(steps == self.step)
                    self.slider.setValue(int(steps[(int(current[0])+frames) % len(steps)] if len(current) else steps[0]))
                return
            self.slider.setValue((self.step + frames) % len(self.calculation.coords))

    def export_image(self):
        if self.builder_editing and self.builder_mode == '2d':
            self.export_sketch('png')
            return
        if not (self.builder_model["atoms"] if self.builder_active else self.calculation) or not self.renderer_ready or self.exporting:
            return
        path, file_filter = QFileDialog.getSaveFileName(self, "Export figure", "molecule.png", "PNG image (*.png);;TIFF image (*.tif *.tiff)")
        if path:
            path = Path(path)
            if not path.suffix:
                path = path.with_suffix(".tif" if "TIFF" in file_filter else ".png")
            self.render_export(path)

    def render_export(self, path):
        if self.exporting or not (self.builder_model["atoms"] if self.builder_active else self.calculation) or not self.renderer_ready or self.builder_state.get("busy", False):
            return
        if Path(path).suffix.lower() not in {".png", ".tif", ".tiff"}:
            QMessageBox.warning(self, "Choose an image format", "Use a .png, .tif, or .tiff filename.")
            return
        self.play.setChecked(False)
        self.vib_play.setChecked(False)
        self.surface_timer.stop()
        if self.builder_active:
            if self.builder_editing:
                self.preview_builder_figure()
        elif not self.comparison_active:
            self.refresh_surface()
        target = self.builder_web if self.builder_active else self.web
        ratio = target.width() / max(1, target.height())
        edge = self.export_size.value()
        width, height = (edge, round(edge / ratio)) if ratio >= 1 else (round(edge * ratio), edge)
        self.image_path = Path(path)
        self.image_dpi = self.export_dpi.value()
        self.exporting = True
        self.export_button.setEnabled(False)
        self.statusBar().showMessage(f"Rendering {width} × {height} pixels…")
        self.begin_export_progress()
        self.send(type="export", width=width, height=height, engine=self.export_engine.currentData(), raySamples=self.ray_samples.value(),
                  samples=self.export_samples.currentData(), transparent=self.transparent.isChecked())

    def save_image(self, data):
        if self.image_path:
            try:
                image = Image.open(BytesIO(base64.b64decode(data.split(",", 1)[1])))
                options = {"dpi": (self.image_dpi, self.image_dpi)}
                if self.image_path.suffix.lower() in {".tif", ".tiff"}:
                    options["compression"] = "tiff_lzw"
                image.save(self.image_path, **options)
                self.statusBar().showMessage(f"Saved {self.image_path.name} · {image.width} × {image.height} px · {self.image_dpi} DPI")
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Export failed", str(error))
            self.end_export_progress()
            self.image_path = None
            self.exporting = False
            self.export_button.setEnabled(True)

    def export_csv(self):
        if not self.calculation:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export energies", "energies.csv", "CSV (*.csv)")
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8") as file:
                    writer = csv.writer(file)
                    writer.writerow(["geometry", "energy_hartree", f"{self.reference.currentText()} ({self.units.currentText()})"])
                    for i, (energy, value) in enumerate(zip(self.calculation.energies, self.plot_values())):
                        writer.writerow([i + 1, energy if np.isfinite(energy) else "", value if np.isfinite(value) else ""])
                self.statusBar().showMessage(f"Saved {Path(path).name}")
            except OSError as error:
                QMessageBox.warning(self, "Export failed", str(error))

    def export_xyz(self):
        if self.builder_active:
            self.export_builder("xyz")
            return
        if not self.calculation:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export geometry", f"geometry-{self.step + 1}.xyz", "XYZ (*.xyz)")
        if path:
            try:
                Path(path).write_text(self.calculation.xyz(self.step), encoding="utf-8")
                self.statusBar().showMessage(f"Saved {Path(path).name}")
            except OSError as error:
                QMessageBox.warning(self, "Export failed", str(error))

    def closeEvent(self, event):
        dialog = getattr(self, "mlip_dialog", None)
        if dialog and ((dialog.setup_task and dialog.setup_task.isRunning()) or dialog.control_process or (hasattr(dialog, "export_task") and dialog.export_task.isRunning())):
            QMessageBox.information(self, "Setup or export in progress", "Wait for the environment operation or trajectory export before closing the application.")
            event.ignore()
            return
        self.mlip_manager.shutdown()
        if self.exporting:
            self.send(type="exportCancel")
            self.end_export_progress()
        self.timer.stop()
        self.pool.waitForDone()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    configure_app(app)
    from .mlip.setup import data_root, read_json
    setup_root = data_root()
    setup_state = read_json(setup_root / 'setup-state.json')
    if (setup_state and not setup_state.get('completed')) or (not setup_state and not (setup_root / 'environments.json').exists()):
        from .setup_ui import SetupWizard
        SetupWizard().exec()
    window = Window()
    window.show()
    paths = [Path(arg) for arg in sys.argv[1:]]
    if paths:
        QTimer.singleShot(0, lambda: window.open_paths(paths))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
