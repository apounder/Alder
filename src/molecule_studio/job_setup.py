"""Gaussian / ORCA input generation from an explicit molecular geometry."""
import re
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSaveFile, QIODevice
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                              QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox,
                              QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from .data import ELEMENTS

JOBS = {'Single point': 'sp', 'Optimization': 'opt', 'Optimization + frequencies': 'optfreq',
        'Frequencies': 'freq', 'Transition state optimization': 'ts', 'IRC': 'irc',
        'Relaxed scan (1D / 2D)': 'scan', 'Excited states (TDDFT / TDA)': 'td'}
METHODS = {'Gaussian': {'PBE0': 'PBE1PBE', 'PBE': 'PBEPBE'}, 'ORCA': {}}


def scan_coordinates(text, coords):
    scans = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        count = {'B': 2, 'A': 3, 'D': 4}.get(parts[0].upper())
        if not count or len(parts) != count+3:
            raise ValueError('Scan rows: B i j increments step; A i j k increments step; D i j k l increments step.')
        ids = [int(v)-1 for v in parts[1:count+1]]
        increments, step = int(parts[-2]), float(parts[-1])
        if len(set(ids)) != count or min(ids)<0 or max(ids)>=len(coords):
            raise ValueError('Scan atom numbers must be unique and between 1 and the atom count.')
        if not 1<=increments<=1000 or not np.isfinite(step) or step == 0:
            raise ValueError('Choose 1–1000 scan increments and a finite, nonzero step.')
        p = np.asarray(coords)[ids]
        if count == 2:
            start = np.linalg.norm(p[1]-p[0])
        elif count == 3:
            a, b = p[0]-p[1], p[2]-p[1]
            norm = np.linalg.norm(a)*np.linalg.norm(b)
            if norm < 1e-12:
                raise ValueError('Scan angle is undefined for coincident atoms.')
            start = np.degrees(np.arccos(np.clip(a@b/norm, -1, 1)))
        else:
            a, b, c = p[1]-p[0], p[2]-p[1], p[3]-p[2]
            n1, n2 = np.cross(a,b), np.cross(b,c)
            if min(np.linalg.norm(n1),np.linalg.norm(n2)) < 1e-12:
                raise ValueError('Scan dihedral is undefined for collinear atoms.')
            start = np.degrees(np.arctan2(np.cross(n1,n2) @ (b/np.linalg.norm(b)), n1@n2))
        end = start+increments*step
        if (count == 2 and min(start,end)<=0) or (count == 3 and not 0<min(start,end)<=max(start,end)<180):
            raise ValueError('Scan distances must stay positive; angles must stay between 0 and 180 degrees.')
        scans.append((parts[0].upper(), ids, increments, step, float(start), float(end)))
    if not 1 <= len(scans) <= 2:
        raise ValueError('Enter one scan coordinate, or two for a nested 2D scan.')
    return scans


def generate_input(atomnos, coords, options):
    atomnos, coords = np.asarray(atomnos), np.asarray(coords, dtype=float)
    if (not len(atomnos) or coords.shape != (len(atomnos), 3) or not np.isfinite(coords).all()
            or np.any(atomnos<1) or np.any(atomnos>=len(ELEMENTS))):
        raise ValueError('Choose a nonempty geometry with valid elements and finite coordinates.')
    engine, job = options['engine'], options['job']
    if engine not in METHODS or job not in JOBS.values():
        raise ValueError('Unknown engine or job type.')
    charge, mult = int(options.get('charge', 0)), int(options.get('multiplicity', 1))
    electrons = int(sum(atomnos))-charge
    if electrons<1 or mult<1 or mult-1>electrons or (electrons-mult+1)%2:
        raise ValueError('Charge and multiplicity are inconsistent with the electron count.')
    method, basis = options.get('method', 'B3LYP').strip(), options.get('basis', 'def2-SVP').strip()
    if any(not re.fullmatch(r'[A-Za-z0-9+*(),_.-]+', value) for value in (method,basis)):
        raise ValueError('Method and basis must each be a single keyword, without spaces or newlines.')
    method = METHODS[engine].get(method, method)
    if job == 'td' and method.upper() == 'MP2':
        raise ValueError('TDDFT/TDA setup requires a DFT or HF reference. Choose a different method.')
    cores, memory = int(options.get('cores', 4)), int(options.get('memory', 8))
    if not 1<=cores<=1024 or not 1<=memory<=65536:
        raise ValueError('Invalid core count or total memory allocation.')
    maxcore = int(memory*1024*0.8/cores)
    if engine == 'ORCA' and maxcore < 1:
        raise ValueError('Increase total memory or reduce the core count: ORCA needs at least 1 MB per process.')
    roots = int(options.get('roots', 10))
    if not 1<=roots<=1000:
        raise ValueError('Choose between 1 and 1000 excited states.')
    solvent = options.get('solvent', '').strip()
    if solvent and not re.fullmatch(r'[A-Za-z0-9_-]+', solvent):
        raise ValueError('Use a solvent keyword such as Water, Acetonitrile or Toluene.')
    solvation = options.get('solvation', 'None')
    if solvation not in {'None','PCM','SMD'}:
        raise ValueError('Unknown solvation model.')
    if solvation!='None' and not solvent:
        raise ValueError('Choose a solvent for the selected solvation model.')
    scans = scan_coordinates(options.get('scan', ''), coords) if job=='scan' else []
    extra = options.get('extra', '').strip()
    if '\n' in extra or '\r' in extra:
        raise ValueError('Additional keywords must fit on a single line.')
    title = ' '.join(options.get('title','Molecule Studio calculation').split()) or 'Molecule Studio calculation'
    geometry = '\n'.join(f'{ELEMENTS[int(z)]:<2} {x: .10f} {y: .10f} {v: .10f}' for z,(x,y,v) in zip(atomnos,coords))
    d3 = options.get('dispersion', False)
    if d3 and method.upper() in {'HF','MP2'}:
        raise ValueError('The D3(BJ) option is for supported DFT functionals. Disable it for HF/MP2.')
    if engine == 'Gaussian':
        basis = {'def2-SVP':'Def2SVP', 'def2-TZVP':'Def2TZVP', 'def2-TZVPP':'Def2TZVPP'}.get(basis,basis)
        keywords = [f'{method}/{basis}', 'SCF=Tight']
        keywords += {'sp':[], 'opt':['Opt'], 'optfreq':['Opt','Freq'], 'freq':['Freq'],
                     'ts':['Opt=(TS,CalcFC)','Freq'], 'irc':['IRC=(CalcFC,MaxPoints=50)'],
                     'scan':['Opt=ModRedundant'],
                     'td':[f'{"TDA" if options.get("tda") else "TD"}=(NStates={roots})']}[job]
        if d3:
            keywords.append('EmpiricalDispersion=GD3BJ')
        if solvation != 'None':
            keywords.append(f'SCRF=({"SMD" if solvation=="SMD" else "IEFPCM"},Solvent={solvent})')
        if extra:
            keywords.append(extra)
        text = f'%chk=calculation.chk\n%mem={memory}GB\n%nprocshared={cores}\n#p {" ".join(keywords)}\n\n{title}\n\n{charge} {mult}\n{geometry}\n\n'
        if scans:
            text += '\n'.join(f'{kind} {" ".join(str(i+1) for i in ids)} S {n} {step:g}' for kind,ids,n,step,_start,_end in scans)+'\n\n'
    else:
        numerical = options.get('numerical', False) or method.upper() == 'MP2'
        frequency = 'NumFreq' if numerical else 'Freq'
        keywords = [method, basis, 'TightSCF']
        keywords += {'sp':['SP'], 'opt':['Opt'], 'optfreq':['Opt',frequency], 'freq':[frequency],
                     'ts':['OptTS',frequency], 'irc':['IRC'], 'scan':['Opt'], 'td':[]}[job]
        if d3:
            keywords.append('D3BJ')
        if solvation == 'PCM':
            keywords.append(f'CPCM({solvent})')
        if extra:
            keywords.append(extra)
        text = f'# {title}\n! {" ".join(keywords)}\n%pal nprocs {cores} end\n%maxcore {maxcore}\n'
        if solvation == 'SMD':
            text += f'%cpcm\n  smd true\n  SMDsolvent "{solvent}"\nend\n'
        if job == 'ts':
            text += '%geom\n  Calc_Hess true\n' + ('  NumHess true\n' if numerical else '') + 'end\n'
        if job == 'irc' and numerical:
            text += '%irc\n  InitHess calc_numfreq\nend\n'
        if job == 'td':
            text += f'%tddft\n  NRoots {roots}\n  TDA {str(bool(options.get("tda"))).lower()}\nend\n'
        if scans:
            text += '%geom\n  Scan\n'
            text += '\n'.join(f'    {kind} {" ".join(str(i) for i in ids)} = {start:.8f}, {end:.8f}, {n+1}' for kind,ids,n,_step,start,end in scans)
            text += '\n  end\nend\n'
        text += f'\n* xyz {charge} {mult}\n{geometry}\n*\n'
    return text


class SetupDialog(QDialog):
    def __init__(self, parent, atomnos, coords, name, charge=0, multiplicity=1):
        from .ui import label
        super().__init__(parent)
        self.atomnos, self.coords = atomnos, coords
        self.setWindowTitle('Calculation setup · Gaussian / ORCA')
        self.resize(980, 740)
        layout = QVBoxLayout(self)
        layout.addWidget(label(f'{name} · {len(atomnos)} atoms · current geometry', 'sectionTitle'))
        layout.addWidget(label('Prepare and save an input file for your installed calculation engine.', 'muted'))
        body = QHBoxLayout()
        layout.addLayout(body, 1)
        content = QWidget()
        form = QFormLayout(content)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        body.addWidget(scroll, 1)
        self.controls = {}
        def combo(key, title, values, editable=False):
            widget = QComboBox()
            widget.addItems(values)
            widget.setEditable(editable)
            form.addRow(title, widget)
            self.controls[key] = widget
            return widget
        def spin(key, title, lo, hi, value):
            widget = QSpinBox()
            widget.setRange(lo,hi)
            widget.setValue(value)
            form.addRow(title,widget)
            self.controls[key] = widget
            return widget
        combo('engine','Engine',['Gaussian','ORCA'])
        combo('job','Job',list(JOBS))
        combo('method','Method',['B3LYP','PBE0','PBE','HF','MP2'], True)
        combo('basis','Basis',['def2-SVP','def2-TZVP','def2-TZVPP','6-31G(d)','cc-pVDZ'], True)
        spin('charge','Charge',-100,100,charge)
        spin('multiplicity','Multiplicity',1,100,multiplicity)
        spin('cores','CPU cores',1,1024,4)
        spin('memory','Total memory (GiB)',1,65536,8)
        form.addRow(label('ORCA: %maxcore gets 80% of this memory budget divided by the core count.', 'muted'))
        combo('solvation','Solvation',['None','PCM','SMD'])
        combo('solvent','Solvent',['Water','Acetonitrile','Toluene','Dichloromethane','Methanol','Ethanol'], True)
        self.controls['dispersion'] = QCheckBox('D3(BJ) dispersion')
        form.addRow(self.controls['dispersion'])
        self.controls['numerical'] = QCheckBox('Numerical frequencies / Hessian (ORCA)')
        self.controls['numerical'].setToolTip('Use for methods without analytic Hessians; automatically used for MP2.')
        form.addRow(self.controls['numerical'])
        spin('roots','Excited states',1,1000,10)
        self.controls['tda'] = QCheckBox('Use Tamm–Dancoff approximation')
        form.addRow(self.controls['tda'])
        self.controls['scan'] = QPlainTextEdit()
        self.controls['scan'].setMaximumHeight(95)
        self.controls['scan'].setPlaceholderText('B 1 2 10 0.1\nD 1 2 3 4 12 15')
        form.addRow('Scan coordinates',self.controls['scan'])
        form.addRow(label('Rows: B/A/D, atom numbers (from 1), increments, step in Å or degrees. Starts at the current geometry. Two rows give a nested 2D scan.', 'muted'))
        self.controls['title'] = QLineEdit(name)
        self.controls['extra'] = QLineEdit()
        form.addRow('Title',self.controls['title'])
        form.addRow('Additional engine keywords',self.controls['extra'])
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        body.addWidget(self.preview, 1)
        self.validation = label('', 'notice')
        layout.addWidget(self.validation)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.save_button = buttons.addButton('Save input…',QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button = buttons.addButton('Copy input',QDialogButtonBox.ButtonRole.ActionRole)
        self.save_button.clicked.connect(self.save)
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.preview.toPlainText()))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for widget in self.controls.values():
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self.refresh)
            elif isinstance(widget,QSpinBox):
                widget.valueChanged.connect(self.refresh)
            elif isinstance(widget,QCheckBox):
                widget.toggled.connect(self.refresh)
            else:
                widget.textChanged.connect(self.refresh)
        self.refresh()

    def options(self):
        result = {}
        for key,widget in self.controls.items():
            result[key] = (widget.currentText() if isinstance(widget,QComboBox) else widget.value() if isinstance(widget,QSpinBox)
                           else widget.isChecked() if isinstance(widget,QCheckBox) else widget.toPlainText() if isinstance(widget,QPlainTextEdit) else widget.text())
        result['job'] = JOBS[result['job']]
        return result

    def refresh(self, *_):
        options = self.options()
        for key in ['roots','tda']:
            self.controls[key].setEnabled(options['job']=='td')
        self.controls['scan'].setEnabled(options['job']=='scan')
        self.controls['solvent'].setEnabled(options['solvation']!='None')
        self.controls['numerical'].setEnabled(options['engine']=='ORCA' and options['job'] in {'optfreq','freq','ts','irc'})
        try:
            text = generate_input(self.atomnos,self.coords,options)
            self.preview.setPlainText(text)
            self.validation.hide()
            valid = True
        except (ValueError,TypeError) as error:
            self.preview.clear()
            self.validation.setText(str(error))
            self.validation.show()
            valid = False
        self.save_button.setEnabled(valid)
        self.copy_button.setEnabled(valid)

    def save(self):
        engine = self.controls['engine'].currentText()
        suffix = '.gjf' if engine=='Gaussian' else '.inp'
        path,_ = QFileDialog.getSaveFileName(self, 'Save calculation input', 'calculation'+suffix,
                                            f'{engine} input (*{suffix});;All files (*)')
        if path:
            try:
                path = Path(path)
                if not path.suffix:
                    path = path.with_suffix(suffix)
                stream = QSaveFile(str(path))
                data = self.preview.toPlainText().encode('utf-8')
                if not stream.open(QIODevice.OpenModeFlag.WriteOnly) or stream.write(data)!=len(data) or not stream.commit():
                    raise OSError(stream.errorString())
                self.parent().statusBar().showMessage(f'Saved {path.name}')
            except OSError as error:
                QMessageBox.warning(self,'Could not save input',str(error))


def open_setup(window):
    if window.builder_active:
        if window.builder_mode == '2d' or window.builder_state.get('busy'):
            QMessageBox.information(window,'Choose a 3D geometry','Switch the builder to 3D and finish generating coordinates before setting up a calculation.')
            return
        model = window.builder_model
        atomnos = np.array([ELEMENTS.index(a['el']) for a in model['atoms']])
        coords = np.array([[a['x'],a['y'],a['z']] for a in model['atoms']])
        name = model['name']
        charge = sum(a.get('charge',0) for a in model['atoms'])
        mult = 1 + ((int(sum(atomnos))-charge)%2)
    elif window.calculation:
        calc = window.calculation
        step = window.step
        if window.comparison_active and window.documents:
            entry = window.documents[window.compare_reference.currentIndex()]
            calc,step = entry['calculation'],entry['step']
        atomnos,coords,name = calc.atomnos,calc.coords[step],calc.name
        try:
            charge,mult = [int(v.strip()) for v in calc.summary.get('Charge / multiplicity','0 / 1').split('/')]
        except ValueError:
            charge,mult = 0,1 + (int(sum(atomnos))%2)
    else:
        atomnos = []
    if not len(atomnos):
        QMessageBox.information(window,'Choose a geometry','Load a calculation or build a 3D molecule first.')
        return
    window.play.setChecked(False)
    window.setup_dialog = SetupDialog(window,atomnos,coords,name,charge,mult)
    window.setup_dialog.setModal(True)
    window.setup_dialog.show()
