"""UV–Vis results panel shared by all supported calculation formats."""
import csv
from pathlib import Path

import numpy as np
from cclib.parser.utils import convertor
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QDoubleSpinBox, QCheckBox, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox)

from .spectra import broaden, wavelength


class UVPanel(QWidget):
    saved = Signal(str)

    def __init__(self):
        super().__init__()
        self.transitions = None
        layout = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setObjectName('muted')
        layout.addWidget(self.note)
        bar = QHBoxLayout()
        self.units = QComboBox()
        self.units.addItems(['nm', 'eV', 'cm⁻¹'])
        self.units.setAccessibleName('Spectrum horizontal axis')
        bar.addWidget(self.units)
        self.shape = QComboBox()
        self.shape.addItems(['Gaussian', 'Lorentzian'])
        self.shape.setAccessibleName('Broadening line shape')
        bar.addWidget(self.shape)
        width_label = QLabel('FWHM / eV')
        bar.addWidget(width_label)
        self.width = QDoubleSpinBox()
        self.width.setRange(.01, 3)
        self.width.setDecimals(2)
        self.width.setSingleStep(.05)
        self.width.setValue(.30)
        self.width.setAccessibleName('Full width at half maximum in electronvolts')
        self.width.setToolTip('Broadening is applied in energy space, also when the axis is wavelength.')
        width_label.setBuddy(self.width)
        bar.addWidget(self.width)
        self.normalize = QCheckBox('Normalize')
        self.normalize.setChecked(True)
        bar.addWidget(self.normalize)
        self.sticks = QCheckBox('Sticks')
        self.sticks.setChecked(True)
        bar.addWidget(self.sticks)
        bar.addStretch()
        layout.addLayout(bar)
        row = QHBoxLayout()
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['#', 'Spin / symmetry', 'eV', 'nm', 'f'])
        self.table.setToolTip('Rows are sorted by energy. Row numbers are not the state numbers printed by the calculation program.')
        self.table.setAccessibleName('Electronic transitions')
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        row.addWidget(self.table, 3)
        self.figure = Figure(figsize=(5, 2.5), layout='constrained', facecolor='white')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setToolTip('Calculated line broadening, not experimental absorbance. Unnormalized intensity is oscillator-strength density per eV on every axis. Use the toolbar to zoom, pan, or save PNG/SVG/PDF figures.')
        self.canvas.setMinimumSize(250, 145)
        self.ax = self.figure.add_subplot()
        self.stick_ax = self.ax.twinx()
        self.canvas.mpl_connect('button_press_event', self.clicked)
        row.addWidget(self.canvas, 4)
        layout.addLayout(row, 1)
        exports = QHBoxLayout()
        self.toolbar = NavigationToolbar2QT(self.canvas, self, coordinates=False)
        exports.addWidget(self.toolbar)
        exports.addStretch()
        self.transitions_export = QPushButton('Transitions CSV')
        self.transitions_export.clicked.connect(lambda: self.export('transitions'))
        exports.addWidget(self.transitions_export)
        self.curve_export = QPushButton('Curve CSV')
        self.curve_export.clicked.connect(lambda: self.export('curve'))
        exports.addWidget(self.curve_export)
        layout.addLayout(exports)
        self.table.currentCellChanged.connect(lambda *_: self.draw())
        for control in (self.units, self.shape):
            control.currentIndexChanged.connect(self.draw)
        self.width.valueChanged.connect(self.draw)
        self.normalize.toggled.connect(self.draw)
        self.sticks.toggled.connect(self.draw)
        self.set_calculation(None)

    def set_calculation(self, calculation):
        self.transitions = calculation.transitions if calculation else None
        t = self.transitions
        self.table.blockSignals(True)
        self.table.setRowCount(len(t.energies) if t else 0)
        if t:
            nm = wavelength(t.energies)
            for i, (energy, strength, symmetry) in enumerate(zip(t.energies, t.strengths, t.symmetries)):
                values = (str(i+1), symmetry or '—', self.number(energy, 4), self.number(nm[i], 2), self.number(strength, 6))
                for col, value in enumerate(values):
                    self.table.setItem(i, col, QTableWidgetItem(value))
            self.table.selectRow(0)
            note = f'{t.method} · {t.source}. Last reported transitions, independent of the geometry slider.'
            missing = int(np.count_nonzero(~np.isfinite(t.strengths)))
            if missing:
                note += f' {missing} missing strengths are omitted from the curve.'
            elif np.all(t.strengths == 0):
                note += ' All reported oscillator strengths are zero.'
        else:
            note = 'No electronic transitions in this file. Open an excited-state Gaussian or ORCA output to plot UV–Vis data.'
        self.note.setText(note)
        self.table.blockSignals(False)
        for control in (self.units, self.shape, self.width, self.normalize, self.sticks, self.transitions_export, self.curve_export):
            control.setEnabled(t is not None)
        self.toolbar.update()
        self.draw()

    @staticmethod
    def number(value, decimals):
        return f'{value:.{decimals}f}' if np.isfinite(value) else '—'

    def curve(self):
        if self.transitions is None:
            return np.empty(0), np.empty(0)
        x, y = broaden(self.transitions, self.width.value(), self.shape.currentText(), self.units.currentText())
        finite = y[np.isfinite(y)]
        if self.normalize.isChecked() and len(finite) and np.max(np.abs(finite)) > 0:
            y = y / np.max(np.abs(finite))
        return x, y

    def draw(self, *_):
        ax, sticks = self.ax, self.stick_ax
        ax.clear()
        sticks.clear()
        sticks.yaxis.set_label_position('right')
        sticks.yaxis.tick_right()
        t = self.transitions
        unit = self.units.currentText()
        sticks.set_visible(bool(t and self.sticks.isChecked()))
        if t:
            x, y = self.curve()
            if np.isfinite(y).any():
                ax.plot(x, y, color='#178b91', linewidth=1.6)
                ax.fill_between(x, y, 0, color='#178b91', alpha=.10)
            else:
                ax.text(.5, .5, 'Oscillator strengths unavailable', ha='center', transform=ax.transAxes, color='#83949d')
            positions = t.positions(unit)
            valid = np.isfinite(positions) & (t.energies > 0)
            known = valid & np.isfinite(t.strengths)
            if sticks.get_visible():
                sticks.vlines(positions[known], 0, t.strengths[known], color='#608ba5', linewidth=.8, alpha=.8)
                sticks.plot(positions[known], t.strengths[known], '.', color='#608ba5', markersize=3)
                sticks.set_ylabel('Oscillator strength (f)', fontsize=8)
                sticks.tick_params(labelsize=8)
            selected = self.table.currentRow()
            if 0 <= selected < len(positions) and valid[selected]:
                ax.axvline(positions[selected], color='#dd7754', linewidth=1, alpha=.8)
            if len(x):
                ax.set_xlim(x[0], x[-1])
        else:
            ax.text(.5, .5, 'No UV–Vis data available', ha='center', transform=ax.transAxes, color='#83949d')
        ax.set_xlabel({'nm': 'Wavelength / nm', 'eV': 'Excitation energy / eV', 'cm⁻¹': 'Wavenumber / cm⁻¹'}[unit], fontsize=9)
        ax.set_ylabel('Normalized intensity' if self.normalize.isChecked() else 'Oscillator-strength density / eV⁻¹', fontsize=8)
        ax.set_title('Calculated absorption', fontsize=9, loc='left')
        ax.tick_params(labelsize=8)
        ax.spines[['top', 'right']].set_visible(False)
        sticks.spines[['top', 'left']].set_visible(False)
        ax.axhline(0, color='#cfdae0', linewidth=.6)
        self.canvas.draw_idle()

    def clicked(self, event):
        if not self.transitions or event.inaxes not in (self.ax, self.stick_ax) or event.xdata is None or self.toolbar.mode:
            return
        positions = self.transitions.positions(self.units.currentText())
        valid = np.flatnonzero(np.isfinite(positions) & (self.transitions.energies > 0))
        if len(valid):
            row = int(valid[np.argmin(np.abs(positions[valid] - event.xdata))])
            self.table.selectRow(row)
            self.table.scrollToItem(self.table.item(row, 0))

    def export(self, kind, path=None):
        t = self.transitions
        if t is None:
            return
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, 'Export UV–Vis data', f'uv-{kind}.csv', 'CSV (*.csv)')
        if not path:
            return
        try:
            with Path(path).open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                if kind == 'transitions':
                    writer.writerow(['row_energy_order', 'symmetry_spin', 'energy_eV', 'wavelength_nm', 'wavenumber_cm-1', 'oscillator_strength', 'method', 'source'])
                    for i, (energy, strength) in enumerate(zip(t.energies, t.strengths)):
                        values = [energy, wavelength([energy])[0], convertor(energy, 'eV', 'wavenumber'), strength]
                        writer.writerow([i+1, t.symmetries[i], *[float(v) if np.isfinite(v) else '' for v in values], t.method, t.source])
                elif kind == 'curve':
                    x, y = self.curve()
                    writer.writerow([f'x_{self.units.currentText()}', 'normalized_intensity' if self.normalize.isChecked() else 'oscillator_strength_density_per_eV', 'shape', 'FWHM_eV'])
                    for a, b in zip(x, y):
                        writer.writerow([a, b if np.isfinite(b) else '', self.shape.currentText(), self.width.value()])
                else:
                    raise ValueError(f'Unknown UV export: {kind}')
            self.saved.emit(f'Saved {Path(path).name}')
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Export failed', str(error))
