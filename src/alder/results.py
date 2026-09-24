"""Reported orbital levels and vibrational modes from the loaded calculation."""
import csv
from pathlib import Path
import numpy as np
from cclib.parser.utils import convertor
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QCheckBox, QComboBox, QSlider,
    QDoubleSpinBox, QFileDialog, QMessageBox)
from .data import ELEMENTS
from .ui import label
from .uv import UVPanel
from .path_view import PathPanel


def result_table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().hide()
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return table


def number(value, decimals=3):
    return f'{value:.{decimals}f}' if np.isfinite(value) else '—'


class ResultsMixin:
    def install_results(self, tabs):
        self.vibration_preview = False
        self.orbital_rows = []
        orbitals = QWidget()
        layout = QVBoxLayout(orbitals)
        bar = QHBoxLayout()
        self.orbital_note = label('No orbital energies in the loaded file.', 'muted')
        bar.addWidget(self.orbital_note, 1)
        self.orbital_units = QComboBox()
        self.orbital_units.addItems(['eV', 'Eh'])
        self.orbital_units.currentIndexChanged.connect(self.update_orbitals)
        bar.addWidget(self.orbital_units)
        self.all_orbitals = QCheckBox('All levels')
        self.all_orbitals.toggled.connect(self.draw_orbitals)
        bar.addWidget(self.all_orbitals)
        save = QPushButton('Export CSV')
        save.clicked.connect(lambda: self.export_results('orbitals'))
        bar.addWidget(save)
        layout.addLayout(bar)
        row = QHBoxLayout()
        self.orbital_table = result_table(['Channel', 'Orbital', 'State', 'Energy / eV'])
        self.orbital_table.currentCellChanged.connect(lambda *_: self.draw_orbitals())
        row.addWidget(self.orbital_table, 3)
        self.orbital_figure = Figure(figsize=(4, 2), layout='constrained', facecolor='white')
        self.orbital_canvas = FigureCanvasQTAgg(self.orbital_figure)
        self.orbital_canvas.setMinimumHeight(145)
        self.orbital_ax = self.orbital_figure.add_subplot()
        self.orbital_canvas.mpl_connect('button_press_event', self.orbital_clicked)
        row.addWidget(self.orbital_canvas, 2)
        layout.addLayout(row)
        tabs.addTab(orbitals, 'Orbital levels')

        modes = QWidget()
        layout = QVBoxLayout(modes)
        self.vibration_note = label('No vibrational frequencies in the loaded file. Open a frequency calculation.', 'muted')
        layout.addWidget(self.vibration_note)
        row = QHBoxLayout()
        self.vibration_table = result_table(['Mode', 'Frequency / cm⁻¹', 'IR / km mol⁻¹', 'Raman / Å⁴ Da⁻¹'])
        self.vibration_table.currentCellChanged.connect(lambda current, *_: self.select_vibration(current))
        row.addWidget(self.vibration_table, 3)
        self.spectrum_figure = Figure(figsize=(4, 2), layout='constrained', facecolor='white')
        self.spectrum_canvas = FigureCanvasQTAgg(self.spectrum_figure)
        self.spectrum_canvas.setMinimumHeight(125)
        self.spectrum_ax = self.spectrum_figure.add_subplot()
        self.spectrum_canvas.mpl_connect('button_press_event', self.spectrum_clicked)
        row.addWidget(self.spectrum_canvas, 2)
        layout.addLayout(row)
        bar = QHBoxLayout()
        self.vib_play = QPushButton('Play mode')
        self.vib_play.setCheckable(True)
        self.vib_play.setEnabled(False)
        self.vib_play.toggled.connect(self.toggle_vibration)
        bar.addWidget(self.vib_play)
        self.vib_reset = QPushButton('Reset position')
        self.vib_reset.clicked.connect(self.reset_vibration)
        self.vib_reset.setEnabled(False)
        bar.addWidget(self.vib_reset)
        self.vib_amplitude = QSlider(Qt.Orientation.Horizontal)
        self.vib_amplitude.setRange(5, 100)
        self.vib_amplitude.setValue(30)
        self.vib_amplitude.setMaximumWidth(120)
        self.vib_amplitude.setAccessibleName('Maximum animation displacement in hundredths of an angstrom')
        self.vib_amplitude.valueChanged.connect(self.vibration_settings)
        self.vib_amplitude_label = label('Amplitude 0.30 Å', 'small')
        bar.addWidget(self.vib_amplitude_label)
        bar.addWidget(self.vib_amplitude)
        bar.addWidget(label('Visual cycles/s', 'small'))
        self.vib_speed = QDoubleSpinBox()
        self.vib_speed.setRange(.1, 3)
        self.vib_speed.setSingleStep(.1)
        self.vib_speed.setValue(.7)
        self.vib_speed.setDecimals(1)
        self.vib_speed.valueChanged.connect(self.vibration_settings)
        bar.addWidget(self.vib_speed)
        save = QPushButton('Export CSV')
        save.clicked.connect(lambda: self.export_results('vibrations'))
        bar.addWidget(save)
        bar.addStretch()
        layout.addLayout(bar)
        self.vibration_tab = tabs.addTab(modes, 'Vibrations')
        self.uv_panel = UVPanel()
        self.uv_panel.saved.connect(self.statusBar().showMessage)
        self.uv_tab = tabs.addTab(self.uv_panel, 'UV–Vis')
        self.path_panel = PathPanel()
        self.path_panel.geometry_selected.connect(self.slider.setValue)
        self.path_panel.trajectory_selected.connect(self.attach_trajectory)
        self.path_panel.saved.connect(self.statusBar().showMessage)
        self.path_tab = tabs.addTab(self.path_panel, 'IRC / Scans')
        tabs.currentChanged.connect(self.results_tab_changed)
        self.refresh_results()

    def refresh_results(self):
        self.update_orbitals()
        self.uv_panel.set_calculation(self.calculation)
        self.path_panel.set_calculation(self.calculation)
        self.path_panel.select_step(self.step)
        calc = self.calculation
        freqs = calc.frequencies if calc else []
        self.vibration_table.blockSignals(True)
        self.vibration_table.setRowCount(len(freqs))
        for i, frequency in enumerate(freqs):
            values = (str(i+1), number(abs(frequency) if frequency<0 else frequency, 2) + (' i' if frequency < 0 else ''),
                      number(calc.ir_intensities[i]), number(calc.raman_activities[i]))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if frequency < 0:
                    item.setForeground(QColor('#b15c22'))
                self.vibration_table.setItem(i, col, item)
        if len(freqs):
            self.vibration_table.selectRow(0)
        self.vibration_table.blockSignals(False)
        self.vibration_note.setText('Select a mode to inspect its displacement. Animation amplitude and speed are visual scales.' if len(freqs)
            else 'No vibrational frequencies in this file. Open a Gaussian/ORCA frequency calculation.')
        self.vib_play.setEnabled(False)
        self.vib_reset.setEnabled(False)
        self.draw_spectrum()
        if self.results.currentIndex() == self.vibration_tab and len(freqs):
            self.select_vibration(0)

    def update_orbitals(self, *_):
        channels = self.calculation.orbitals if self.calculation else []
        unit = self.orbital_units.currentText()
        self.orbital_table.blockSignals(True)
        self.orbital_rows = [(c, i) for c, channel in enumerate(channels) for i in range(len(channel['energies']))]
        self.orbital_table.setRowCount(len(self.orbital_rows))
        self.orbital_table.setHorizontalHeaderLabels(['Channel', 'Orbital', 'State', f'Energy / {unit}'])
        frontier = 0
        for row, (c, i) in enumerate(self.orbital_rows):
            channel = channels[c]
            h = channel['homo']
            state = 'Unknown' if h is None else ('Occupied' if i <= h else 'Virtual')
            title = str(i+1)
            if h is not None and i == h:
                title += ' · HOMO'
                if c == 0: frontier = row
            elif h is not None and i == h+1: title += ' · LUMO'
            energy = channel['energies'][i]
            if unit == 'Eh': energy = convertor(energy, 'eV', 'hartree')
            for col, value in enumerate((channel['spin'], title, state, number(energy, 6))):
                self.orbital_table.setItem(row, col, QTableWidgetItem(value))
        if self.orbital_rows:
            self.orbital_table.selectRow(frontier)
            self.orbital_table.scrollToItem(self.orbital_table.item(frontier, 0))
        self.orbital_table.blockSignals(False)
        gaps = []
        for channel in channels:
            h, energies = channel['homo'], channel['energies']
            if h is not None and 0 <= h < len(energies)-1:
                gaps.append(f"{channel['spin']} gap {energies[h+1]-energies[h]:.3f} eV")
        self.orbital_note.setText('Last reported orbital energies · ' + (' · '.join(gaps) or 'Occupations unavailable') if channels
                                 else 'No orbital energies printed in this file.')
        self.draw_orbitals()

    def draw_orbitals(self, *_):
        ax = self.orbital_ax
        ax.clear()
        channels = self.calculation.orbitals if self.calculation else []
        unit = self.orbital_units.currentText()
        selected = self.orbital_table.currentRow()
        selected_pair = self.orbital_rows[selected] if 0 <= selected < len(self.orbital_rows) else None
        for c, channel in enumerate(channels):
            energies, h = channel['energies'], channel['homo']
            indices = set(range(len(energies))) if self.all_orbitals.isChecked() or h is None else set(range(max(0, h-5), min(len(energies), h+7)))
            if selected_pair and selected_pair[0] == c: indices.add(selected_pair[1])
            for i in sorted(indices):
                y = energies[i] if unit == 'eV' else convertor(energies[i], 'eV', 'hartree')
                if not np.isfinite(y): continue
                chosen = selected_pair == (c, i)
                ax.hlines(y, c-.28, c+.28, color='#dd7754' if chosen else '#14793b' if h is not None and i<=h else '#608ba5', linewidth=2.2 if chosen else 1.1)
                if h is not None and i in (h, h+1):
                    ax.annotate('HOMO' if i==h else 'LUMO', (c+.3, y), fontsize=8, va='center')
        ax.set_xticks(range(len(channels)), [c['spin'] for c in channels])
        ax.set_ylabel(f'Orbital energy / {unit}', fontsize=9)
        ax.set_xlim(-.5, max(.6, len(channels)-.2))
        ax.tick_params(labelsize=8)
        ax.spines[['top','right']].set_visible(False)
        if not channels: ax.text(.5,.5,'No orbital levels available',ha='center',transform=ax.transAxes,color='#83949d')
        self.orbital_canvas.draw_idle()

    def orbital_clicked(self, event):
        channels = self.calculation.orbitals if self.calculation else []
        if event.inaxes != self.orbital_ax or event.xdata is None or not channels: return
        c = max(0,min(len(channels)-1,round(event.xdata)))
        values = channels[c]['energies']
        y = event.ydata if self.orbital_units.currentText()=='eV' else convertor(event.ydata,'hartree','eV')
        finite = np.flatnonzero(np.isfinite(values))
        if not len(finite): return
        i = int(finite[np.argmin(np.abs(values[finite]-y))])
        row = self.orbital_rows.index((c,i))
        self.orbital_table.selectRow(row)
        self.orbital_table.scrollToItem(self.orbital_table.item(row,0))

    def draw_spectrum(self):
        ax = self.spectrum_ax
        ax.clear()
        calc = self.calculation
        if calc is not None and len(calc.frequencies):
            has_ir = np.isfinite(calc.ir_intensities).any()
            values = calc.ir_intensities if has_ir else np.ones(len(calc.frequencies))
            ax.vlines(calc.frequencies,0,values,color='#14793b',linewidth=1)
            i = self.vibration_table.currentRow()
            if 0 <= i < len(values): ax.axvline(calc.frequencies[i],color='#dd7754',linewidth=1.5)
            ax.set_ylabel('IR / km mol⁻¹' if has_ir else 'Mode markers',fontsize=8)
        else: ax.text(.5,.5,'No frequencies available',ha='center',transform=ax.transAxes,color='#83949d')
        ax.set_xlabel('Wavenumber / cm⁻¹',fontsize=9)
        ax.tick_params(labelsize=8)
        ax.spines[['top','right']].set_visible(False)
        self.spectrum_canvas.draw_idle()

    def spectrum_clicked(self, event):
        if self.calculation is None or not len(self.calculation.frequencies) or event.inaxes!=self.spectrum_ax or event.xdata is None: return
        i = int(np.argmin(np.abs(self.calculation.frequencies-event.xdata)))
        self.vibration_table.selectRow(i)
        self.vibration_table.scrollToItem(self.vibration_table.item(i,0))

    def results_tab_changed(self, index):
        if index==self.vibration_tab and not self.builder_active:
            self.select_vibration(self.vibration_table.currentRow())
        else: self.stop_vibration()

    def select_vibration(self, index):
        calc = self.calculation
        self.draw_spectrum()
        if calc is None or not 0 <= index < len(calc.frequencies) or self.results.currentIndex()!=self.vibration_tab or self.builder_active: return
        self.play.setChecked(False)
        if not self.vibration_preview and calc.vibration_coords is not None:
            rmsd=np.sqrt(np.mean(np.sum((calc.coords-calc.vibration_coords)**2,axis=2),axis=1))
            matches=np.flatnonzero(rmsd<1e-4)
            if len(matches):
                index_step=int(matches[-1])
                self.slider.setValue(index_step)
                if self.step!=index_step:self.select_step(index_step)
            else:
                self.energy_label.setText('No energy associated with this vibration geometry')
                self.relative_label.setText('See Energy profile for evaluated optimization steps')
                self.convergence_label.setText('')
        self.vibration_preview = True
        self.timeline_widget.setEnabled(False)
        points = calc.vibration_coords.copy() if calc.vibration_coords is not None else calc.coords[-1].copy()
        vectors = calc.displacements[index].copy() if calc.displacements is not None else None
        # Cube registration rotates the displayed geometry and its vectors together.
        if self.display_coords is not None:
            source,target = calc.coords[-1],self.display_coords[-1]
            u,_,vt = np.linalg.svd((source-source.mean(axis=0)).T@(target-target.mean(axis=0)))
            rotation = u@np.diag([1,1,np.linalg.det(u@vt)])@vt
            points = (points-source.mean(axis=0))@rotation+target.mean(axis=0)
            if vectors is not None: vectors = vectors@rotation
        valid = bool(vectors is not None and np.linalg.norm(vectors,axis=1).max()>1e-12)
        self.vib_play.setEnabled(valid)
        self.vib_reset.setEnabled(valid)
        if not valid:
            self.vib_play.blockSignals(True);self.vib_play.setChecked(False);self.vib_play.blockSignals(False)
        self.vib_play.setText('Pause mode' if self.vib_play.isChecked() else 'Play mode')
        freq = calc.frequencies[index]
        note = f'Mode {index+1} · {freq:.2f} cm⁻¹ · '
        note += 'Imaginary mode: oscillation is illustrative.' if freq<0 else 'Visual amplitude and speed; equilibrium geometry is preserved.'
        if not valid: note += ' Displacement vectors are unavailable; animation is disabled.'
        self.vibration_note.setText(note)
        xyz = '\n'.join([str(len(points)),f'{calc.name} | mode {index+1}']+[f'{ELEMENTS[int(z)]} {x:.9f} {y:.9f} {v:.9f}' for z,(x,y,v) in zip(calc.atomnos,points)])+'\n'
        self.send(type='vibration',xyz=xyz,vectors=vectors.tolist() if valid else None,mode=index+1,
                  amplitude=self.vib_amplitude.value()/100,rate=self.vib_speed.value(),playing=valid and self.vib_play.isChecked())
        self.step_label.setText(f'Vibration geometry · mode {index+1} · {freq:.2f} cm⁻¹')

    def toggle_vibration(self, checked):
        if checked and not self.vibration_preview:
            self.select_vibration(self.vibration_table.currentRow())
        self.vib_play.setText('Pause mode' if checked else 'Play mode')
        self.vibration_settings()

    def vibration_settings(self, *_):
        self.vib_amplitude_label.setText(f'Amplitude {self.vib_amplitude.value()/100:.2f} Å')
        if self.vibration_preview:
            self.send(type='vibrationSettings',amplitude=self.vib_amplitude.value()/100,rate=self.vib_speed.value(),playing=self.vib_play.isChecked())

    def reset_vibration(self):
        self.vib_play.setChecked(False)
        if self.vibration_preview: self.send(type='vibrationSettings',reset=True,playing=False)

    def stop_vibration(self, restore=True):
        if not getattr(self,'vibration_preview',False): return
        self.vibration_preview = False
        self.vib_play.blockSignals(True);self.vib_play.setChecked(False);self.vib_play.blockSignals(False)
        self.vib_play.setText('Play mode')
        self.timeline_widget.setEnabled(True)
        self.send(type='vibrationStop')
        if restore and self.calculation:
            self.select_step(self.step)
            self.refresh_surface()

    def export_results(self, kind, path=None):
        if not self.calculation: return
        if path is None:
            path,_ = QFileDialog.getSaveFileName(self,'Export reported results',kind+'.csv','CSV (*.csv)')
        if not path: return
        calc = self.calculation
        try:
            with Path(path).open('w',newline='',encoding='utf-8') as stream:
                writer = csv.writer(stream)
                if kind=='orbitals':
                    writer.writerow(['channel','orbital_1_based','state','energy_eV','energy_Eh'])
                    for channel in calc.orbitals:
                        h = channel['homo']
                        for i,e in enumerate(channel['energies']):
                            writer.writerow([channel['spin'],i+1,'unknown' if h is None else 'occupied' if i<=h else 'virtual', e if np.isfinite(e) else '',convertor(e,'eV','hartree') if np.isfinite(e) else ''])
                else:
                    writer.writerow(['mode_1_based','frequency_cm-1','IR_km_per_mol','Raman_A4_per_Da'])
                    for i,f in enumerate(calc.frequencies):
                        writer.writerow([i+1,f,*[float(v) if np.isfinite(v) else '' for v in (calc.ir_intensities[i],calc.raman_activities[i])]])
            self.statusBar().showMessage(f'Saved {Path(path).name}')
        except OSError as error: QMessageBox.warning(self,'Export failed',str(error))
