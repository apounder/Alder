"""Selectable IRC profiles and one-/two-dimensional potential-energy scans."""
import csv
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QFileDialog, QMessageBox)

ENERGY_UNITS = {'kcal/mol': 627.509474, 'kJ/mol': 2625.499639, 'Eh': 1.0}


class PathPanel(QWidget):
    geometry_selected = Signal(int)
    trajectory_selected = Signal(str)
    saved = Signal(str)

    def __init__(self):
        super().__init__()
        self.path = None
        self.colorbar = None
        layout = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setObjectName('muted')
        layout.addWidget(self.note)
        bar = QHBoxLayout()
        self.units = QComboBox()
        self.units.addItems(ENERGY_UNITS)
        self.units.setAccessibleName('Path energy units')
        bar.addWidget(self.units)
        self.reference = QComboBox()
        self.reference.addItems(['Relative to minimum', 'Relative to first point', 'As reported'])
        self.reference.setAccessibleName('Path energy reference')
        bar.addWidget(self.reference)
        self.attach = QPushButton('Attach IRC trajectory…')
        self.attach.setToolTip('Choose the matching ORCA _IRC_Full_trj.xyz file to animate its path.')
        self.attach.clicked.connect(self.choose_trajectory)
        bar.addWidget(self.attach)
        bar.addStretch()
        layout.addLayout(bar)
        row = QHBoxLayout()
        self.table = QTableWidget()
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        row.addWidget(self.table, 2)
        self.figure = Figure(figsize=(5, 2.5), layout='constrained', facecolor='white')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumSize(260, 155)
        self.ax = self.figure.add_subplot()
        self.canvas.mpl_connect('button_press_event', self.clicked)
        row.addWidget(self.canvas, 3)
        layout.addLayout(row, 1)
        bar = QHBoxLayout()
        self.toolbar = NavigationToolbar2QT(self.canvas, self, coordinates=False)
        bar.addWidget(self.toolbar)
        bar.addStretch()
        self.export_button = QPushButton('Path CSV')
        self.export_button.clicked.connect(lambda: self.export())
        bar.addWidget(self.export_button)
        layout.addLayout(bar)
        self.table.currentCellChanged.connect(self.row_changed)
        self.table.cellClicked.connect(lambda row, _: self.show_geometry(row))
        self.units.currentIndexChanged.connect(self.refresh)
        self.reference.currentIndexChanged.connect(self.refresh)
        self.set_calculation(None)

    def set_calculation(self, calculation):
        self.path = calculation.reaction_path if calculation else None
        self.attach.setVisible(bool(self.path and self.path.kind == 'IRC'))
        for control in (self.units, self.reference, self.export_button):
            control.setEnabled(self.path is not None)
        self.toolbar.update()
        self.refresh()

    def values(self):
        if self.path is None:
            return np.empty(0)
        values = self.path.energies.copy()
        finite = values[np.isfinite(values)]
        if len(finite):
            if self.reference.currentIndex() == 0:
                values -= finite.min()
            elif self.reference.currentIndex() == 1:
                values -= finite[0]
        return values * ENERGY_UNITS[self.units.currentText()]

    def refresh(self, *_):
        p = self.path
        current = self.table.currentRow()
        self.table.blockSignals(True)
        headers = ['Point', *(p.labels if p else ['Coordinate']), 'E−ETS / Eh' if p and p.relative else 'Energy / Eh', self.units.currentText(), 'Geometry']
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(p.energies) if p else 0)
        if p:
            for i, (parameters, energy, displayed, step) in enumerate(zip(p.parameters, p.energies, self.values(), p.steps)):
                fields = [str(i+1), *[f'{v:.5f}' for v in parameters], f'{energy:.8f}' if np.isfinite(energy) else '—',
                          f'{displayed:.5f}' if np.isfinite(displayed) else '—', str(step+1) if step >= 0 else 'Unavailable']
                for col, value in enumerate(fields):
                    self.table.setItem(i, col, QTableWidgetItem(value))
            self.table.selectRow(min(max(current, 0), len(p.energies)-1))
        self.table.blockSignals(False)
        self.update_note()
        self.draw()

    def update_note(self):
        p = self.path
        if p is None:
            self.note.setText('Open an IRC or potential-energy scan to inspect its path or 2D energy map.')
            return
        text = f'{p.kind} · {len(p.energies)} reported points. Select a point to show its geometry; Play follows linked path points.'
        if p.kind == 'Scan':
            text += ' Missing or unconverged grid points are not interpolated.'
        if np.any(p.steps < 0):
            text += ' Some geometries are unavailable.'
            if p.kind == 'IRC':
                text += ' Attach the matching full IRC XYZ trajectory.'
        selected = self.table.currentRow()
        if 0 <= selected < len(p.steps) and p.steps[selected] < 0:
            text += ' This point has no linked geometry; the viewer retains its previous geometry.'
        self.note.setText(text)

    def draw(self):
        if self.colorbar is not None:
            self.colorbar.remove()
            self.colorbar = None
        ax = self.ax
        ax.clear()
        p = self.path
        energy_label = ('E−ETS' if p and p.relative and self.reference.currentIndex() == 2 else 'E' if self.reference.currentIndex() == 2 else 'ΔE') + f' / {self.units.currentText()}'
        if p is None:
            ax.text(.5, .5, 'No IRC or scan data', ha='center', transform=ax.transAxes, color='#83949d')
        elif p.parameters.shape[1] == 2:
            xy, values = p.parameters, self.values()
            valid = np.isfinite(xy).all(axis=1) & np.isfinite(values)
            if valid.any():
                x, y = [np.unique(xy[np.isfinite(xy[:, i]), i]) for i in range(2)]
                if len(x) > 1 and len(y) > 1 and len(x)*len(y) <= 1_000_000:
                    grid = np.full((len(y), len(x)), np.nan)
                    for (a, b), energy in zip(xy[valid], values[valid]):
                        grid[np.searchsorted(y, b), np.searchsorted(x, a)] = energy
                    artist = ax.pcolormesh(x, y, np.ma.masked_invalid(grid), shading='nearest', cmap='viridis')
                else:
                    artist = ax.scatter(xy[valid, 0], xy[valid, 1], c=values[valid], cmap='viridis', marker='s', s=80)
                self.colorbar = self.figure.colorbar(artist, ax=ax, label=energy_label, pad=.02)
                self.colorbar.ax.tick_params(labelsize=8)
            selected = self.table.currentRow()
            if 0 <= selected < len(xy) and np.isfinite(xy[selected]).all():
                ax.plot(*xy[selected], 'o', markerfacecolor='none', markeredgecolor='#ef8056', markersize=9, markeredgewidth=2)
            ax.set_xlabel(p.labels[0], fontsize=8)
            ax.set_ylabel(p.labels[1], fontsize=8)
        else:
            x = p.parameters[:, 0] if p.parameters.shape[1] == 1 else np.arange(1, len(p.energies)+1)
            order = np.argsort(x, kind='stable')
            ax.plot(x[order], self.values()[order], 'o-', color='#178b91', markersize=3, linewidth=1.3)
            selected = self.table.currentRow()
            if 0 <= selected < len(x):
                ax.axvline(x[selected], color='#dd7754', linewidth=1)
            ax.set_xlabel(p.labels[0] if p.parameters.shape[1] == 1 else 'Point (higher-dimensional scan)', fontsize=8)
            ax.set_ylabel(energy_label, fontsize=8)
        ax.spines[['top', 'right']].set_visible(False)
        ax.tick_params(labelsize=8)
        self.canvas.draw_idle()

    def row_changed(self, row, *_):
        if self.path is None or not 0 <= row < len(self.path.steps):
            return
        self.update_note()
        self.draw()
        self.show_geometry(row)

    def show_geometry(self, row):
        if self.path is None or not 0 <= row < len(self.path.steps):
            return
        if self.path.steps[row] >= 0:
            self.geometry_selected.emit(int(self.path.steps[row]))

    def select_step(self, step):
        if self.path is None:
            return
        matches = np.flatnonzero(self.path.steps == step)
        if len(matches) and self.table.currentRow() != matches[0]:
            self.table.blockSignals(True)
            self.table.selectRow(int(matches[0]))
            self.table.blockSignals(False)
            self.update_note()
            self.draw()

    def clicked(self, event):
        p = self.path
        if p is None or event.inaxes != self.ax or event.xdata is None or self.toolbar.mode:
            return
        xy = p.parameters
        if xy.shape[1] == 2 and event.ydata is not None:
            span = np.ptp(xy, axis=0)
            distances = np.linalg.norm((xy-[event.xdata, event.ydata])/np.where(span > 0, span, 1), axis=1)
        else:
            x = xy[:, 0] if xy.shape[1] == 1 else np.arange(1, len(xy)+1)
            distances = np.abs(x-event.xdata)
        finite = np.flatnonzero(np.isfinite(distances))
        if len(finite):
            row = int(finite[np.argmin(distances[finite])])
            self.table.selectRow(row)
            self.show_geometry(row)
            self.table.scrollToItem(self.table.item(row, 0))

    def choose_trajectory(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Attach full IRC trajectory', '', 'XYZ trajectories (*.xyz)')
        if path:
            self.trajectory_selected.emit(path)

    def export(self, path=None):
        if self.path is None:
            return
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, 'Export IRC / scan points', 'path.csv', 'CSV (*.csv)')
        if not path:
            return
        try:
            p = self.path
            with Path(path).open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                writer.writerow(['point', *p.labels, 'energy_relative_to_TS_Eh' if p.relative else 'energy_Eh', f'{self.reference.currentText()}_{self.units.currentText()}', 'geometry_1_based'])
                for i, (parameters, energy, value, step) in enumerate(zip(p.parameters, p.energies, self.values(), p.steps)):
                    writer.writerow([i+1, *parameters, energy if np.isfinite(energy) else '', value if np.isfinite(value) else '', step+1 if step >= 0 else ''])
            self.saved.emit(f'Saved {Path(path).name}')
        except OSError as error:
            QMessageBox.warning(self, 'Export failed', str(error))
