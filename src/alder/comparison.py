"""Multiple calculation documents and a shared-renderer structure overlay."""
import csv
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QHBoxLayout,
                              QHeaderView, QLineEdit, QMessageBox, QPushButton, QSpinBox,
                              QTableWidget, QTableWidgetItem)

from .alignment import atom_pairs, rigid_fit
from .ui import inspector_page, label

COLORS = ['#4477aa', '#ee7733', '#228833', '#cc3377', '#aa4499', '#66ccee', '#bbbb33']


class ComparisonMixin:
    def install_comparison(self):
        self.documents = []
        self.comparison_active = False
        self.comparison_results = []
        side = inspector_page(self.inspector, 'Compare')
        self.compare_tab = self.inspector.count() - 1
        side.addWidget(label('Structure overlay', 'sectionTitle'))
        side.addWidget(label('Open multiple outputs, then choose a reference and geometry for each structure. Original coordinates are preserved.', 'muted'))
        add = QPushButton('Add outputs / trajectories')
        add.clicked.connect(self.choose_comparison_files)
        side.addWidget(add)
        self.compare_reference = QComboBox()
        self.compare_reference.currentIndexChanged.connect(self.comparison_reference_changed)
        side.addWidget(label('Reference structure'))
        side.addWidget(self.compare_reference)
        self.compare_table = QTableWidget(0, 3)
        self.compare_table.setHorizontalHeaderLabels(['Show / structure', 'Frame', 'Color'])
        self.compare_table.verticalHeader().hide()
        self.compare_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2):
            self.compare_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.compare_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.compare_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.compare_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.compare_table.setMinimumHeight(170)
        self.compare_table.itemChanged.connect(self.comparison_visibility)
        self.compare_table.itemSelectionChanged.connect(self.comparison_mapping_selected)
        side.addWidget(self.compare_table)
        self.compare_solid = QCheckBox('Solid color per structure')
        self.compare_solid.setChecked(True)
        self.compare_solid.toggled.connect(self.refresh_comparison)
        side.addWidget(self.compare_solid)
        self.compare_align = QCheckBox('Align to reference (rotation + translation)')
        self.compare_align.setChecked(True)
        self.compare_align.toggled.connect(lambda: self.refresh_comparison(fit=True))
        side.addWidget(self.compare_align)
        self.compare_heavy = QCheckBox('Use heavy atoms for alignment / RMSD')
        self.compare_heavy.setChecked(True)
        self.compare_heavy.toggled.connect(self.refresh_comparison)
        side.addWidget(self.compare_heavy)
        self.compare_report = label('Load at least two structures to compare.', 'small')
        self.compare_report.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        side.addWidget(self.compare_report)
        side.addWidget(label('Atom mapping for selected row'))
        self.compare_mapping = QLineEdit()
        self.compare_mapping.setPlaceholderText('Automatic: same element order')
        self.compare_mapping.setToolTip('Reference:moving atom numbers, starting at 1. Example: 1:3, 2:1, 3:2. Explicit pairs override the heavy-atom filter.')
        self.compare_mapping.editingFinished.connect(self.comparison_mapping_changed)
        side.addWidget(self.compare_mapping)
        side.addWidget(label('RMSD uses equal atom weights and the listed correspondence; equivalent atoms are not automatically permuted. Explicit mapping can select a shared fragment.', 'muted'))
        row = QHBoxLayout()
        for title, callback in [('Remove selected', self.remove_comparison_document), ('Export RMSD', self.export_comparison)]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        side.addLayout(row)
        side.addStretch()

    def choose_comparison_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Add structures to compare', '',
            'Outputs / trajectories (*.log *.out *.xyz *.extxyz *.traj);;All files (*)')
        if paths:
            self.open_paths([Path(p) for p in paths], compare=True)

    def add_document(self, calculation, replace=False):
        if replace:
            entry = next((d for d in self.documents if d['calculation'] is self.calculation), None)
        else:
            entry = None
        if entry is None:
            color = next((c for c in COLORS if all(d['color'] != c for d in self.documents)), COLORS[len(self.documents) % len(COLORS)])
            entry = dict(calculation=calculation, step=len(calculation.coords)-1, visible=True,
                         color=color, mapping='')
            self.documents.append(entry)
        else:
            if entry['calculation'] is not calculation:
                self.send(type='renameDocument', key=str(id(entry['calculation'])), newKey=str(id(calculation)))
            entry['calculation'] = calculation
            entry['step'] = len(calculation.coords)-1
        self.rebuild_documents()

    def rebuild_documents(self, reference=None):
        if reference is None:
            reference = self.compare_reference.currentIndex()
        for combo in (self.calculation_picker, self.compare_reference):
            combo.blockSignals(True)
            combo.clear()
            for i, entry in enumerate(self.documents):
                combo.addItem(f'{i+1}. {entry["calculation"].name}')
            if combo is self.compare_reference:
                combo.setCurrentIndex(max(0, min(reference, len(self.documents)-1)))
            else:
                combo.setCurrentIndex(next((i for i, d in enumerate(self.documents) if d['calculation'] is self.calculation), -1))
            combo.blockSignals(False)
        self.compare_table.blockSignals(True)
        self.compare_table.setRowCount(len(self.documents))
        for i, entry in enumerate(self.documents):
            calc = entry['calculation']
            item = QTableWidgetItem(f'{i+1}. {calc.name}')
            item.setToolTip(calc.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if entry['visible'] else Qt.CheckState.Unchecked)
            self.compare_table.setItem(i, 0, item)
            frame = QSpinBox()
            frame.setRange(1, len(calc.coords))
            frame.setValue(entry['step'] + 1)
            frame.setKeyboardTracking(False)
            frame.setAccessibleName(f'Geometry for {calc.name}')
            frame.setStyleSheet('padding: 3px 4px;')
            frame.valueChanged.connect(lambda value, entry=entry: self.comparison_frame_changed(entry, value-1))
            self.compare_table.setCellWidget(i, 1, frame)
            color = QPushButton('●')
            color.setToolTip('Choose a solid color for this structure')
            color.setStyleSheet(f'color: {entry["color"]}; font-size: 20px; padding: 2px 8px;')
            color.clicked.connect(lambda checked=False, entry=entry, color=color: self.comparison_color(entry, color))
            self.compare_table.setCellWidget(i, 2, color)
        self.compare_table.blockSignals(False)
        self.comparison_mapping_selected()

    def choose_calculation(self, index):
        if 0 <= index < len(self.documents) and not self.busy:
            entry = self.documents[index]
            self.activate_calculation(entry['calculation'], entry['step'])

    def comparison_frame_changed(self, entry, step):
        entry['step'] = step
        self.refresh_comparison()

    def comparison_reference_changed(self, _index):
        # Explicit pairs belong to a particular reference, not just its row number.
        had_mapping = any(entry['mapping'] for entry in self.documents)
        for entry in self.documents:
            entry['mapping'] = ''
        self.compare_mapping.clear()
        if had_mapping:
            self.statusBar().showMessage('Reference changed; enter new atom mappings for this reference.')
        self.refresh_comparison(fit=True)

    def comparison_visibility(self, item):
        if item.column() == 0:
            self.documents[item.row()]['visible'] = item.checkState() == Qt.CheckState.Checked
            self.refresh_comparison(fit=True)

    def comparison_color(self, entry, button):
        color = QColorDialog.getColor(QColor(entry['color']), self, 'Structure color')
        if color.isValid():
            entry['color'] = color.name()
            button.setStyleSheet(f'color: {color.name()}; font-size: 20px; padding: 2px 8px;')
            self.compare_solid.setChecked(True)
            self.refresh_comparison()

    def comparison_mapping_selected(self):
        row = self.compare_table.currentRow()
        self.compare_mapping.setText(self.documents[row]['mapping'] if 0 <= row < len(self.documents) else '')

    def comparison_mapping_changed(self):
        row = self.compare_table.currentRow()
        if 0 <= row < len(self.documents):
            self.documents[row]['mapping'] = self.compare_mapping.text()
            self.refresh_comparison(fit=True)

    def show_comparison(self):
        self.play.setChecked(False)
        self.stop_vibration(restore=False)
        self.builder_active = self.builder_editing = False
        self.comparison_active = True
        self.viewer_stack.setCurrentWidget(self.web)
        self.builder_command(type='visibility', visible=False)
        self.send(type='visibility', visible=True)
        self.timeline_widget.hide()
        self.results.hide()
        self.filename.setText('Structure comparison')
        self.refresh_comparison(fit=True)

    def refresh_comparison(self, *_args, fit=False):
        if not getattr(self, 'comparison_active', False):
            return
        index = self.compare_reference.currentIndex()
        if not 0 <= index < len(self.documents):
            self.send(type='comparison', structures=[], fit=True)
            self.compare_report.setText('Load at least two structures to compare.')
            self.export_button.setEnabled(False)
            return
        reference = self.documents[index]
        ref = reference['calculation']
        target = ref.coords[reference['step']]
        structures, reports, rows = [], [], []
        for i, entry in enumerate(self.documents):
            if not entry['visible']:
                continue
            calc = entry['calculation']
            points = calc.coords[entry['step']].copy()
            try:
                a, b = atom_pairs(ref.atomnos, calc.atomnos, self.compare_heavy.isChecked(),
                                  entry['mapping'] if entry is not reference else '')
                rotation, translation, rmsd = rigid_fit(points[b], target[a])
                raw = float(np.sqrt(np.mean(np.sum((points[b]-target[a])**2, axis=1))))
                if self.compare_align.isChecked():
                    points = points @ rotation + translation
                energy = calc.energies[entry['step']]
                rows.append([calc.name, entry['step']+1, ref.name, reference['step']+1, len(a), raw, rmsd,
                             energy if np.isfinite(energy) else '', ' '.join(f'{x+1}:{y+1}' for x,y in zip(a,b))])
                if entry is not reference:
                    reports.append(f'{i+1}. {calc.name}\n{len(a)} atom pairs · RMSD {rmsd:.5f} Å aligned\nUnaligned {raw:.5f} Å')
                    if len(a) < 3 or np.linalg.matrix_rank(target[a]-target[a].mean(axis=0), tol=1e-7) < 2:
                        reports.append('Fit atoms are fewer than 3 or collinear; rotation is not uniquely determined.')
            except ValueError as error:
                reports.append(f'{i+1}. {calc.name}: {error}\nDisplayed in original coordinates; RMSD unavailable.')
            xyz = calc.xyz(0, points[None])
            structures.append(dict(xyz=xyz, color=entry['color'] if self.compare_solid.isChecked() else None,
                                   name=calc.name, annotationKey=str(id(calc))))
        self.comparison_results = rows
        self.compare_report.setText('\n\n'.join(reports) or 'Show another structure to calculate its RMSD against the reference.')
        self.send(type='comparison', structures=structures, fit=fit)
        self.export_button.setEnabled(bool(structures) and self.renderer_ready and not self.exporting)

    def remove_comparison_document(self):
        row = self.compare_table.currentRow()
        if self.busy or not 0 <= row < len(self.documents):
            return
        reference = self.compare_reference.currentIndex()
        removed = self.documents.pop(row)
        self.send(type='forgetDocument', key=str(id(removed['calculation'])))
        if row == reference:
            for entry in self.documents:
                entry['mapping'] = ''
            self.compare_mapping.clear()
        if row < reference:
            reference -= 1
        if removed['calculation'] is self.calculation:
            self.calculation = None
            self.clear_cube()
            if self.documents:
                self.activate_calculation(self.documents[0]['calculation'], self.documents[0]['step'])
            else:
                self.slider.setRange(0, 0)
                self.play.setEnabled(False)
                self.details.setText('Open a calculation or trajectory.')
                self.warning.hide()
                self.energy_label.setText('—')
                self.table.setRowCount(0)
                self.draw_plot()
                self.refresh_results()
        self.rebuild_documents(reference)
        self.inspector.setCurrentIndex(self.compare_tab)
        self.show_comparison()

    def export_comparison(self):
        if not self.comparison_results:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export alignment results', 'comparison.csv', 'CSV (*.csv)')
        if path:
            try:
                with open(path, 'w', newline='', encoding='utf-8') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(['structure', 'frame', 'reference', 'reference_frame', 'atom_pairs',
                                     'unaligned_rmsd_angstrom', 'aligned_rmsd_angstrom', 'energy_hartree', 'reference:moving_atoms'])
                    writer.writerows(self.comparison_results)
                self.statusBar().showMessage(f'Saved {Path(path).name}')
            except OSError as error:
                QMessageBox.warning(self, 'Export failed', str(error))
