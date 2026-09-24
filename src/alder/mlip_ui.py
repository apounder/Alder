"""Native calculation setup, persistent job queue, environment and model management."""
from copy import deepcopy
import json
import os
import sys
from pathlib import Path
import time
import numpy as np
from ase.data import atomic_masses
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, QStandardPaths, QLockFile, QThread, Signal, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from .data import ELEMENTS
from .mlip.contract import DEFAULTS, snapshot, coordinate, digest
from .mlip.registry import CATALOGUE, specification, validate_model
from .mlip.store import Store
from .mlip.offline import bundle_directory
from .mlip.environment import atomic_json, managed_environment, managed_python, redact, process_alive, external_environment, external_libraries
from .mlip_results import calculation_page

JOB_NAMES={'Single point':'sp','Geometry optimization':'opt','Constrained optimization':'constrained',
    'Frequencies':'freq','Optimize → frequencies':'optfreq','Relaxed 1D / 2D scan':'scan',
    'Sella transition state':'ts','Intrinsic reaction coordinate':'irc','NEB / climbing-image NEB':'neb',
    'Molecular dynamics':'md','Sample conformers':'conformers'}


def button(text,callback):
    b=QPushButton(text);b.clicked.connect(callback);return b


def note(text):
    w=QLabel(text);w.setWordWrap(True);w.setTextFormat(Qt.TextFormat.PlainText);return w


def start_external(process,python,args):
    """Do not inject frozen GUI DLLs into an independent calculator interpreter."""
    env=QProcessEnvironment()
    for key,value in external_environment().items():env.insert(key,value)
    process.setProcessEnvironment(env)
    with external_libraries():process.start(python,args)


class SetupTask(QThread):
    message=Signal(str);done=Signal(str);failed=Signal(str)
    def __init__(self,root,backend,parent):super().__init__(parent);self.root=root;self.backend=backend
    def run(self):
        try:self.done.emit(managed_environment(self.root,self.backend,self.message.emit,self.isInterruptionRequested))
        except Exception as error:self.failed.emit(redact(error))


class JobManager(QObject):
    changed=Signal()
    def __init__(self,window,root=None):
        super().__init__(window);self.window=window
        self.root=Path(root or os.environ.get('ALDER_MLIP_HOME') or (Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))/'calculations-v1'))
        self.root.mkdir(parents=True,exist_ok=True);self.store=Store(self.root/'jobs.sqlite')
        self.config_file=self.root/'environments.json'
        try:self.config=json.loads(self.config_file.read_text())
        except (OSError,ValueError):self.config={}
        self.lock=QLockFile(str(self.root/'queue.lock'));self.owns_queue=self.lock.tryLock(0)
        self.process=None;self.active=None;self.closing=False;self.preparing=None
        if self.owns_queue:
            for job in self.store.jobs():
                worker=self.store.artifact(job['id'],'worker')
                if job['status']=='running' and not (worker and process_alive(worker['pid'])):
                    self.store.state(job['id'],'interrupted','Application/worker stopped before completion; saved frames retained.')
        self.timer=QTimer(self);self.timer.setInterval(500);self.timer.timeout.connect(self.tick);self.timer.start()
    def persist(self):atomic_json(self.config_file,self.config)
    def worker(self):return str(Path(__file__).with_name('mlip')/'worker.py')
    def python(self,backend):return self.config.get(backend,{}).get('python','')
    def tick(self):
        if self.closing:return
        if self.process is None and self.owns_queue and self.preparing is None:
            jobs=self.store.jobs()
            # A worker alive during startup can exit after its old desktop dies.
            # Reconcile it on subsequent ticks so it cannot block the queue forever.
            for job in jobs:
                worker=self.store.artifact(job['id'],'worker') if job['status']=='running' else None
                if worker and not process_alive(worker['pid']):
                    self.store.state(job['id'],'interrupted','Previous worker stopped; saved frames/checkpoint retained.')
                    job['status']='interrupted'
            queued=[] if any(j['status']=='running' for j in jobs) else [j for j in reversed(jobs) if j['status']=='queued']
            if queued:
                job=self.store.job(queued[0]['id']);backend=job['input']['model']['backend'];python=self.python(backend)
                if python and Path(python).is_file():self.start(job['id'],python)
        self.changed.emit()
    def start(self,ident,python):
        self.active=ident;self.process=QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.output)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)
        start_external(self.process,python,[self.worker(),'run','--db',str(self.store.path),'--job',ident,'--cache',str(self.root/'models'),'--workdir',str(self.root/'work'),'--parent-pid',str(os.getpid())])
    def output(self):
        if self.process and self.active:
            text=redact(bytes(self.process.readAllStandardOutput()).decode('utf-8','replace'))
            # Preserve useful logs while bounding single writes from verbose libraries.
            if text.strip():self.store.event(self.active,text[-16000:].strip())
    def process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            self.store.state(self.active,'failed','Could not start the selected Python environment. Reconnect/check it in setup.')
            self.finished(-1,QProcess.ExitStatus.CrashExit)
    def finished(self,code,status):
        if self.process is None:return
        self.output();job=self.store.job(self.active)
        if job['status'] in ('queued','running'):
            self.store.state(self.active,'cancelled' if job['cancel'] else 'interrupted',
                'Worker exited without a final record; partial frames/checkpoint retained.')
        self.process.deleteLater();self.process=None;self.active=None;self.changed.emit()
    def cancel(self,ident):
        if self.store.job(ident)['status']=='waiting':
            workflow=self.store.artifact(ident,'workflow')
            if workflow:self.cancel(workflow['child'])
            self.store.state(ident,'cancelled')
        self.store.cancel(ident)
        if ident==self.active:
            process=self.process
            # Cooperative cancel is checked at every evaluation; bound a hung native kernel.
            QTimer.singleShot(5000,lambda:process.kill() if self.process is process and process.state()!=QProcess.ProcessState.NotRunning else None)
    def shutdown(self):
        self.closing=True;self.timer.stop()
        if self.process:
            self.process.kill();self.process.waitForFinished(3000)
        if self.owns_queue:self.lock.unlock()
        self.store.close()


def capture(window):
    if window.builder_active:
        if window.builder_mode!='3d' or window.builder_state.get('busy'):raise ValueError('Finish generating a 3D builder geometry first.')
        model=deepcopy(window.builder_model);atoms=model['atoms'];numbers=[ELEMENTS.index(a['el']) for a in atoms]
        charge=sum(a.get('charge',0) for a in atoms);masses=[]
        from rdkit import Chem
        pt=Chem.GetPeriodicTable()
        for a,z in zip(atoms,numbers):masses.append(pt.GetMassForIsotope(z,a['isotope']) if a.get('isotope') else float(atomic_masses[z]))
        s=dict(name=model['name'],numbers=numbers,positions=[[a['x'],a['y'],a['z']] for a in atoms],bonds=model['bonds'],
            formal_charges=[a.get('charge',0) for a in atoms],masses=masses,charge=charge,multiplicity=1+((sum(numbers)-charge)%2))
    elif window.calculation:
        calc=window.calculation;step=window.step
        if window.comparison_active and window.documents:
            entry=window.documents[window.compare_reference.currentIndex()];calc=entry['calculation'];step=entry['step']
        s=deepcopy(calc.metadata.get('mlip_input',{}))
        s.update(name=calc.name,numbers=calc.atomnos.tolist(),positions=calc.coords[step].tolist(),pbc=[bool(calc.metadata.get('periodic',False))]*3)
        if 'charge' not in s:
            try:s['charge'],s['multiplicity']=[int(v.strip()) for v in calc.summary.get('Charge / multiplicity','0 / 1').split('/')]
            except ValueError:s.update(charge=0,multiplicity=1+int(sum(calc.atomnos))%2)
        if calc.metadata.get('simulation_frames'):
            original=calc.metadata['simulation_frames'][step]
            for key,value in original.items():s[key]=value.tolist() if isinstance(value,np.ndarray) else deepcopy(value)
            if 'multiplicity' not in original:s['multiplicity']=int(original.get('spin',original.get('mult',s['multiplicity'])))
            s['charge']=int(s['charge'])
        if calc.metadata.get('mlip_rows'):
            row=calc.metadata['mlip_rows'][step]
            for key in ('masses','cell','pbc','velocities'):
                if key in row:s[key]=deepcopy(row[key])
    else:raise ValueError('Build or import a molecular structure, or select a calculation/Compare frame first.')
    if not s.get('numbers'):raise ValueError('Choose a nonempty structure.')
    return s


class MLIPDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.manager=window.mlip_manager;self.store=self.manager.store
        self.setWindowTitle('Local MLIP calculations');self.resize(1050,790);self.setModal(False)
        self.structure=None;self.parent_job=None;self.product=None;self.check_results={};self.control_process=None;self.setup_task=None
        self.automatic=False;self.setup_cancelled=False
        self.setup_lock=QLockFile(str(self.manager.root/'setup.lock'))
        layout=QVBoxLayout(self);self.tabs=QTabWidget();layout.addWidget(self.tabs)
        self.make_setup();self.make_jobs();self.make_environment()
        self.manager.changed.connect(self.refresh_jobs)
        self.model_changed();self.refresh_jobs()
    def page(self,title):
        widget=QWidget();layout=QVBoxLayout(widget);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(widget);self.tabs.addTab(scroll,title)
        return layout
    def safe(self,fn):
        try:return fn()
        except Exception as error:QMessageBox.warning(self,'Local calculation',redact(error));return None
    def make_setup(self):
        layout=self.page('Calculation')
        row=QHBoxLayout();row.addWidget(button('Capture current Build / calculation / Compare frame',lambda:self.safe(self.capture_input)))
        row.addWidget(button('Import starting structure…',self.import_structure));layout.addLayout(row)
        self.input_label=note('Capture a 3D structure. The queued input is an immutable snapshot.');layout.addWidget(self.input_label)
        form=QFormLayout();layout.addLayout(form)
        self.charge=QSpinBox();self.charge.setRange(-100,100);self.mult=QSpinBox();self.mult.setRange(1,101);self.mult.setValue(1)
        form.addRow('Total charge',self.charge);form.addRow('Spin multiplicity (2S+1)',self.mult)
        self.backend=QComboBox();self.backend.addItems(['mace','aimnet2','uma']);self.backend.currentTextChanged.connect(self.backend_changed)
        self.checkpoint=QComboBox();self.checkpoint.currentTextChanged.connect(self.model_changed)
        self.device=QComboBox();self.device.addItem('cpu');self.precision=QComboBox()
        self.task=QLineEdit();self.head=QLineEdit()
        form.addRow('Calculator',self.backend);form.addRow('Checkpoint',self.checkpoint);form.addRow('Device',self.device);form.addRow('Precision',self.precision)
        form.addRow('Task',self.task);form.addRow('Head',self.head)
        self.local=QLineEdit();self.local.setPlaceholderText('Optional compatible local model file')
        localrow=QHBoxLayout();localrow.addWidget(self.local);localrow.addWidget(button('Browse…',self.choose_local));form.addRow('Local checkpoint',localrow)
        self.manifest=QPlainTextEdit();self.manifest.setPlaceholderText('Local checkpoint capability manifest (JSON); required only for local files.');self.manifest.setMaximumHeight(90);form.addRow('Local manifest',self.manifest)
        self.domain=note('');layout.addWidget(self.domain)
        layout.addWidget(button('Guided setup — models and CPU/GPU…',lambda:self.safe(self.guided_setup)))
        self.ack=QCheckBox('I understand the model’s chemical domain and will validate reaction-path predictions.');layout.addWidget(self.ack)
        self.job=QComboBox()
        for name,key in JOB_NAMES.items():self.job.addItem(name,key)
        form.addRow('Job',self.job)
        self.fields={};self.settings_form=form
        for label,key,kind,values in [
            ('Optimizer','optimizer','choice',['BFGS','LBFGS','FIRE']),('Force threshold / eV Å⁻¹','fmax','float',None),
            ('Maximum steps / MD steps','steps','int',None),('Maximum optimizer step / Å','maxstep','float',None),
            ('Hessian','hessian','choice',['auto','analytical','finite_difference']),('FD displacement / Å','displacement','float',None),
            ('Finite difference points','nfree','choice',[2,4]),('MD ensemble','ensemble','choice',['nvt','nve']),
            ('MD timestep / fs','timestep','float',None),('Temperature / K','temperature','float',None),
            ('Langevin friction / fs⁻¹','friction','float',None),('Trajectory interval / steps','stride','int',None),
            ('Random seed','seed','int',None),('IRC direction','direction','choice',['both','forward','reverse']),
            ('IRC mass-weighted step','irc_dx','float',None),('Total NEB images','images','int',None),
            ('NEB interpolation','interpolation','choice',['idpp','linear']),('NEB spring / eV Å⁻²','spring','float',None),
            ('Conformer candidates','candidates','int',None),('Energy window / eV','energy_window','float',None),
            ('Heavy-atom RMSD threshold / Å','rmsd','float',None)]:
            if kind=='choice':
                widget=QComboBox()
                for value in values:widget.addItem(str(value),value)
                widget.setCurrentIndex(widget.findData(DEFAULTS[key]))
            elif kind=='int':widget=QSpinBox();widget.setRange(0 if key=='seed' else 1,2147483647 if key=='seed' else 10000000);widget.setValue(DEFAULTS[key])
            else:widget=QDoubleSpinBox();widget.setDecimals(6);widget.setRange(0,100000);widget.setValue(DEFAULTS[key])
            widget.setAccessibleName(label);self.fields[key]=widget;form.addRow(label,widget)
        for key,label in [('climb','Climbing-image NEB'),('verify_ts','Verify TS with frequencies'),('endpoint_opt','Queue IRC endpoint optimizations')]:
            w=QCheckBox(label);w.setChecked(DEFAULTS[key]);self.fields[key]=w;form.addRow(w)
        self.constraints=QPlainTextEdit();self.constraints.setMaximumHeight(90)
        self.constraints.setPlaceholderText('freeze 1 2 3\nbond 1 4 1.50\nangle 1 4 5 109.5\ndihedral 1 4 5 6 -60')
        form.addRow('Constraints (one-based atoms)',self.constraints)
        self.scans=QPlainTextEdit();self.scans.setMaximumHeight(70);self.scans.setPlaceholderText('bond 1 2 1.0 2.0 11\ndihedral 1 2 3 4 -180 180 25')
        form.addRow('Scans: kind, atoms, start, stop, points',self.scans)
        self.pick_kind=QComboBox();self.pick_kind.addItems(['bond','angle','dihedral','freeze'])
        pickrow=QHBoxLayout();pickrow.addWidget(self.pick_kind);pickrow.addWidget(button('Pick in viewer',self.begin_pick));pickrow.addWidget(button('Use picked atoms',lambda:self.safe(self.use_picks)));layout.addLayout(pickrow)
        layout.addWidget(note('Picking uses the shared Measure tool. Minimize this window if it covers the canvas, click atoms in order, then use the selection. Numerical indices are one-based.'))
        row=QHBoxLayout();row.addWidget(button('Capture current frame as NEB product',lambda:self.safe(self.capture_product)))
        self.mapping=QLineEdit();self.mapping.setPlaceholderText('Product atom indices, in reactant order: 1 2 3 …');row.addWidget(self.mapping);layout.addLayout(row)
        self.product_label=note('NEB product is not selected.');layout.addWidget(self.product_label)
        self.advanced=QPlainTextEdit();self.advanced.setPlainText('{}');self.advanced.setMaximumHeight(100)
        form.addRow('Advanced settings (JSON overrides)',self.advanced)
        layout.addWidget(note('Advanced keys: dt (FIRE), sella_eta, sella_gamma, sella_delta, sella_internal, irc_inner_fmax, irc_inner_steps, imaginary_threshold, md_max_temperature, md_max_force, threads. All settings are saved with the job.'))
        self.queue_button=button('Queue local calculation',lambda:self.safe(self.submit));self.queue_button.setObjectName('primary');layout.addWidget(self.queue_button)
        self.job.currentIndexChanged.connect(self.job_changed)
        self.job_changed()
        self.backend_changed()
    def job_changed(self):
        kind=self.job.currentData()
        groups={
            'optimizer':{'opt','constrained','optfreq','scan','neb','conformers'},
            'maxstep':{'opt','constrained','optfreq','scan','neb','conformers'},
            'steps':set(JOB_NAMES.values())-{'sp','freq'},
            'fmax':set(JOB_NAMES.values())-{'sp','md'},
            'hessian':{'freq','optfreq','ts','irc'},'displacement':{'freq','optfreq','ts','irc'},'nfree':{'freq','optfreq','ts','irc'},
            'ensemble':{'md'},'timestep':{'md'},'temperature':{'md'},'friction':{'md'},'stride':{'md'},
            'seed':{'md','conformers'},'direction':{'irc'},'irc_dx':{'irc'},'endpoint_opt':{'irc'},
            'images':{'neb'},'interpolation':{'neb'},'spring':{'neb'},'climb':{'neb'},
            'candidates':{'conformers'},'energy_window':{'conformers'},'rmsd':{'conformers'},'verify_ts':{'ts'}}
        for key,w in self.fields.items():
            visible=kind in groups.get(key,{kind});w.setVisible(visible)
            label=self.settings_form.labelForField(w)
            if label:label.setVisible(visible)
        self.constraints.setEnabled(kind in {'opt','constrained','optfreq','freq','scan','md'})
        self.scans.setEnabled(kind=='scan');self.mapping.setEnabled(kind=='neb')
    def backend_changed(self):
        if not hasattr(self,'checkpoint'):return
        b=self.backend.currentText();self.checkpoint.blockSignals(True);self.checkpoint.clear()
        for name,spec in CATALOGUE.items():
            if spec['backend']==b:self.checkpoint.addItem(name)
        if b=='mace':self.checkpoint.setCurrentText('MACE-ANI-CC')
        self.checkpoint.blockSignals(False)
        if hasattr(self,'environment_path'):self.environment_path.setText(self.manager.python(b))
        if hasattr(self,'domain'):self.model_changed()
    def model_changed(self):
        if not hasattr(self,'domain'):return
        spec=CATALOGUE.get(self.checkpoint.currentText())
        if not spec:return
        self.precision.clear();self.precision.addItems(spec['precision']);self.precision.setCurrentText('float64' if spec['backend']=='mace' else 'float32')
        self.task.setText(spec['task'] or '');self.head.setText(spec['head'] or '')
        if hasattr(self,'license_ack'):self.license_ack.setChecked(False)
        if hasattr(self,'setup_target'):self.setup_target.setText('Selected: '+spec['backend']+' / '+spec['name'])
        self.domain.setText(spec['domain']+'\nCorrections: '+spec['correction']+'\n'+spec.get('license','Public AIMNetCentral checkpoint.'))
        cfg=self.manager.config.get(self.backend.currentText(),{});self.device.clear();self.device.addItems(cfg.get('probe',{}).get('devices',[]) or ['cpu'])
        if cfg.get('preferred_device') in cfg.get('probe',{}).get('devices',[]):self.device.setCurrentText(cfg['preferred_device'])
    def model_config(self):
        c=dict(backend=self.backend.currentText(),checkpoint=self.checkpoint.currentText(),device=self.device.currentText(),precision=self.precision.currentText(),
               task=self.task.text().strip() or None,head=self.head.text().strip() or None,corrections='checkpoint',domain_ack=self.ack.isChecked())
        if self.local.text().strip():c.update(local_file=self.local.text().strip(),manifest=json.loads(self.manifest.toPlainText()))
        ready=self.check_results.get(self.model_key(c))
        if ready:c['sha256']=ready['sha256']
        return c
    def model_key(self,c):return digest({k:v for k,v in c.items() if k not in ('domain_ack','sha256')})
    def choose_local(self):
        path,_=QFileDialog.getOpenFileName(self,'Compatible local checkpoint','','Model (*.pt *.model *.pth);;All files (*)')
        if path:self.local.setText(path)
    def capture_input(self):
        self.structure=capture(self.window);self.parent_job=None
        self.charge.setValue(self.structure['charge']);self.mult.setValue(self.structure['multiplicity'])
        self.constraints.clear()
        self.restore_input_constraints()
        self.input_label.setText(f'{self.structure["name"]} · {len(self.structure["numbers"])} atoms captured. Confirm charge and multiplicity; they are editable, not inferred by the calculator.')
    def restore_input_constraints(self):
        for c in self.structure.get('ase_constraints',[]):
            name=c['name'];kw=c['kwargs']
            if name=='FixAtoms':self.constraints.appendPlainText('freeze '+' '.join(str(i+1) for i in kw['indices']))
            elif name=='FixInternals':
                for key,kind in [('bonds','bond'),('angles_deg','angle'),('dihedrals_deg','dihedral')]:
                    for target,ids in kw.get(key,[]) or []:
                        target=coordinate(self.structure['positions'],ids) if target is None else target
                        self.constraints.appendPlainText(kind+' '+' '.join(str(i+1) for i in ids)+f' {target}')
                if kw.get('bondcombos'):raise ValueError('Imported linear-combination constraints are not supported; explicitly prepare a compatible input.')
            elif name=='FixBondLengths':
                for ids in kw['pairs']:
                    self.constraints.appendPlainText('bond '+' '.join(str(i+1) for i in ids)+f" {coordinate(self.structure['positions'],ids)}")
            else:raise ValueError(f'Imported constraint {name} cannot be converted automatically; prepare a supported input instead of silently dropping it.')
    def import_structure(self):
        path,_=QFileDialog.getOpenFileName(self,'Import starting structure','','Structures (*.xyz *.extxyz *.traj *.mol *.sdf *.pdb)')
        if path:self.window.open_paths([Path(path)]);self.input_label.setText('Importing structure. Once visible, capture its selected 3D frame.');self.showMinimized()
    def capture_product(self):
        self.product=capture(self.window);self.product_label.setText(f'Product: {self.product["name"]} · {len(self.product["numbers"])} atoms. Enter and review explicit atom correspondence.')
    def begin_pick(self):
        if self.window.comparison_active and self.window.documents:
            entry=self.window.documents[self.window.compare_reference.currentIndex()]
            self.window.activate_calculation(entry['calculation'],entry['step'])
        kind=self.pick_kind.currentText();n={'bond':2,'angle':3,'dihedral':4,'freeze':2}[kind]
        self.window.measurement_kind.setCurrentIndex(self.window.measurement_kind.findData(n));self.window.measure_button.setChecked(True);self.window.choose_measurement(True)
        self.showMinimized()
    def use_picks(self):
        bridge=self.window.builder_bridge if self.window.builder_active else self.window.bridge
        state=self.window.measurement_states.get(bridge,{})
        ids=state.get('indices',[])
        if not ids:raise ValueError('Pick atoms with Measure in the viewer first.')
        if self.structure is None:self.capture_input()
        now=capture(self.window)
        if now['numbers']!=self.structure['numbers'] or not np.allclose(now['positions'],self.structure['positions'],atol=1e-5):
            raise ValueError('Viewer geometry differs from the captured input. Capture it again before using atom picks.')
        kind=self.pick_kind.currentText()
        text=kind+' '+' '.join(str(i+1) for i in ids)
        if kind!='freeze':
            count={'bond':2,'angle':3,'dihedral':4}[kind]
            if len(ids)!=count:raise ValueError(f'Pick exactly {count} atoms.')
            val=coordinate(self.structure['positions'],ids)
            if self.job.currentData()=='scan':text+=f' {val:.6f} {val+(0.5 if kind=="bond" else 30):.6f} 11'
            else:text+=f' {val:.6f}'
        (self.scans if self.job.currentData()=='scan' and kind!='freeze' else self.constraints).appendPlainText(text)
    def parse_rows(self,widget,scan=False):
        result=[]
        for line in widget.toPlainText().splitlines():
            words=line.split()
            if not words:continue
            kind=words[0].lower();count={'bond':2,'angle':3,'dihedral':4}.get(kind)
            if kind=='freeze' and not scan:result.append(dict(kind=kind,atoms=[int(v)-1 for v in words[1:]]));continue
            if count is None or len(words)!=1+count+(3 if scan else 1):raise ValueError('Invalid constraint/scan row; follow the displayed format.')
            d=dict(kind=kind,atoms=[int(v)-1 for v in words[1:1+count]])
            if scan:d.update(start=float(words[-3]),stop=float(words[-2]),points=int(words[-1]))
            else:d['value']=float(words[-1])
            result.append(d)
        return result
    def settings(self):
        result={}
        for key,w in self.fields.items():
            result[key]=w.currentData() if isinstance(w,QComboBox) else w.isChecked() if isinstance(w,QCheckBox) else w.value()
        extra=json.loads(self.advanced.toPlainText());unknown=set(extra)-set(DEFAULTS)
        if unknown:raise ValueError('Unknown advanced settings: '+', '.join(sorted(unknown)))
        result.update(extra);result['scans']=self.parse_rows(self.scans,True) if self.scans.isEnabled() else []
        if self.job.currentData()=='neb':result.update(product=self.product,mapping=[int(v)-1 for v in self.mapping.text().replace(',',' ').split()])
        return result
    def submit(self):
        if self.setup_busy():raise ValueError('Wait for the current model check or setup operation to finish.')
        if self.structure is None:self.capture_input()
        s=deepcopy(self.structure);s.update(charge=self.charge.value(),multiplicity=self.mult.value())
        c=self.model_config();kind=self.job.currentData();validate_model(c,s,kind)
        env=self.manager.config.get(c['backend'],{});probe=env.get('probe',{})
        if not probe.get('ready') or c['device'] not in probe.get('devices',[]):
            self.tabs.setCurrentIndex(2)
            raise ValueError('Choose Set up selected model to prepare this calculator and check the selected device.')
        if kind in ('ts','irc') and not probe.get('sella'):raise ValueError('This environment cannot import Sella. See its setup log or connect a compatible environment.')
        data=snapshot(s,c,kind,self.settings(),self.parse_rows(self.constraints) if self.constraints.isEnabled() else [],self.parent_job)
        if self.model_key(c) not in self.check_results:
            # Readiness is session-local. Recheck cached weights after reopening,
            # then queue exactly the input captured by this click.
            self.environment_path.setText(self.manager.python(c['backend']))
            self.tabs.setCurrentIndex(2)
            def checked(result):
                if not result.get('ready'):
                    self.readiness.setText('Nothing queued. Model check failed: '+result.get('error','No readiness result.')+' Use Set up selected model to prepare or repair this checkpoint.')
                    return
                data['model']['sha256']=result['sha256']
                self.enqueue(data)
            self.model_action('check',checked,config=c,structure=s)
            return
        self.enqueue(data)
    def enqueue(self,data):
        ident=self.store.submit(data);self.tabs.setCurrentIndex(1);self.refresh_jobs();self.select_job(ident)
    def make_jobs(self):
        layout=self.page('Jobs / results');self.jobs_table=QTableWidget(0,5);self.jobs_table.setHorizontalHeaderLabels(['Job','Type','State','Elapsed','Progress'])
        self.jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.jobs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.jobs_table.itemSelectionChanged.connect(self.show_job);layout.addWidget(self.jobs_table)
        row=QHBoxLayout()
        for title,fn in [('Cancel',self.cancel_job),('Open saved page',self.open_page),('Open job folder',self.open_folder),('Export trajectory…',self.export_frames),('Inspect frame / forces',self.inspect_frame)]:row.addWidget(button(title,lambda checked=False,fn=fn:self.safe(fn)))
        layout.addLayout(row);page=QHBoxLayout();self.page_start=QSpinBox();self.page_start.setRange(1,2147483647);self.page_start.setValue(1)
        self.page_count=QSpinBox();self.page_count.setRange(1,1000);self.page_count.setValue(200)
        page.addWidget(note('First saved frame'));page.addWidget(self.page_start);page.addWidget(note('Page size'));page.addWidget(self.page_count);layout.addLayout(page)
        row=QHBoxLayout();self.next_job=QComboBox()
        for name,key in JOB_NAMES.items():self.next_job.addItem(name,key)
        row.addWidget(self.next_job);row.addWidget(button('Use selected viewer frame as child input',lambda:self.safe(self.seed_child)));layout.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Continue exact MD checkpoint',lambda:self.safe(self.continue_md)))
        row.addWidget(button('Restart from last saved geometry',lambda:self.safe(self.restart_geometry)))
        row.addWidget(button('Compare retained conformers / IRC endpoints',lambda:self.safe(self.compare_results)));layout.addLayout(row)
        self.result_table=QTableWidget(0,6);self.result_table.setHorizontalHeaderLabels(['Point / rank','Target','Achieved','Energy / eV','Status','Saved frame'])
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.result_table.cellDoubleClicked.connect(lambda row,col:self.safe(lambda:self.open_result(row)));layout.addWidget(self.result_table)
        self.live_preview=QCheckBox('Live last-frame preview (at most once per second)');layout.addWidget(self.live_preview)
        self.last_live_time=0.;self.last_live_frame=None
        tools=QHBoxLayout();tools.addWidget(button('Open final points / band',lambda:self.safe(self.open_final_points)));tools.addWidget(button('Plot MD diagnostics',lambda:self.safe(self.plot_md)));layout.addLayout(tools)
        self.job_detail=QPlainTextEdit();self.job_detail.setReadOnly(True);self.job_detail.setMinimumHeight(160);layout.addWidget(self.job_detail)
        self.logs=QPlainTextEdit();self.logs.setReadOnly(True);self.logs.setMaximumBlockCount(500);layout.addWidget(self.logs)
        layout.addWidget(note('Exact continuation is available for saved NVE/Langevin MD checkpoints. Geometry restart creates a new job and does not restore optimizer/Sella history. Use frame pages for long trajectories; the full data stay on disk.'))
    def selected_job(self):
        row=self.jobs_table.currentRow()
        if row<0:raise ValueError('Select a job first.')
        return self.jobs_table.item(row,0).data(Qt.ItemDataRole.UserRole)
    def select_job(self,ident):
        for row in range(self.jobs_table.rowCount()):
            if self.jobs_table.item(row,0).data(Qt.ItemDataRole.UserRole)==ident:self.jobs_table.selectRow(row);break
    def refresh_jobs(self):
        if not hasattr(self,'jobs_table') or not self.isVisible():return
        try:selected=self.selected_job()
        except ValueError:selected=None
        rows=self.store.jobs();self.jobs_table.blockSignals(True);self.jobs_table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            data=self.store.job(row['id'])['input'];elapsed=(row['finished'] or time.time())-(row['started'] or time.time())
            p=row['progress'];values=[row['id'][:8],data['kind'],row['status'],f'{max(0,elapsed):.0f} s',f'{p.get("phase","")} {p.get("iteration","")}/{p.get("maximum","")}']
            for col,value in enumerate(values):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row['id']);self.jobs_table.setItem(i,col,item)
        if selected:self.select_job(selected)
        self.jobs_table.blockSignals(False)
        if selected:
            self.show_job()
            n=self.store.count(selected)
            if self.live_preview.isChecked() and n and self.last_live_frame!=(selected,n) and time.monotonic()-self.last_live_time>=1:
                calc=calculation_page(self.store,selected,indices=[n-1])
                current=self.window.calculation
                self.window.add_document(calc,replace=bool(current and current.metadata.get('mlip_job')==selected))
                self.window.activate_calculation(calc)
                self.last_live_time=time.monotonic();self.last_live_frame=(selected,n)
    def show_job(self):
        try:ident=self.selected_job()
        except ValueError:return
        job=self.store.job(ident);data=job['input'];n=self.store.count(ident)
        details=dict(state=job['status'],error=job['error'],frames=n,parent=data.get('parent'),progress=job['progress'],input_hash=job['input_hash'],
            provenance=self.store.artifact(ident,'provenance'),optimization=self.store.artifact(ident,'optimization'),saddle=self.store.artifact(ident,'saddle'),md=self.store.artifact(ident,'md'))
        if n:
            last=self.store.get_frame(ident,n-1);details['last_frame']={k:v for k,v in last.items() if k not in ('positions','forces','velocities','masses')}
        text=json.dumps(details,indent=2,ensure_ascii=False)
        if text!=self.job_detail.toPlainText():self.job_detail.setPlainText(text)
        self.result_rows(ident)
        logs='\n'.join(time.strftime('%H:%M:%S',time.localtime(t))+' '+m for t,m in self.store.events(ident))
        if logs!=self.logs.toPlainText():self.logs.setPlainText(logs);self.logs.verticalScrollBar().setValue(self.logs.verticalScrollBar().maximum())
    def result_rows(self,ident):
        records=[]
        scan=self.store.artifact(ident,'scan');neb=self.store.artifact(ident,'neb');conf=self.store.artifact(ident,'conformers');irc=self.store.artifact(ident,'irc')
        if scan:
            records=[(str(p['index']),str(p['targets']),str(p['achieved']),p['energy'],p['status'],p['frame']) for p in scan['points']]
        elif neb:
            records=[(str(p['image']+1),'','',p['energy'],'NEB image (not verified TS)',p['frame']) for p in neb['history'][-1]['images']]
        elif conf:
            ranks={p['candidate']:p['rank'] for p in conf['retained']}
            records=[(f"Candidate {p['candidate']+1}; rank {ranks.get(p['candidate'],'discarded')}",'','',p['energy'],p['status']+(' / connectivity changed' if p.get('connectivity_changed') else ''),p['frame']) for p in conf['candidates']]
        elif irc:
            records=[(b['direction'],str(p['coordinate']),'',p['energy'],b['termination'],p['frame']) for b in irc['branches'] for p in b['points']]
        # Every point is on disk; bound the native table and provide paging.
        first=max(0,self.page_start.value()-1);records=records[first:first+self.page_count.value()]
        signature=json.dumps(records)
        if signature==getattr(self,'last_result_rows',None):return
        self.last_result_rows=signature;self.result_table.setRowCount(len(records))
        for row,record in enumerate(records):
            for col,value in enumerate(record):
                text='' if value is None else str(value+1) if col==5 else str(value)
                item=QTableWidgetItem(text);item.setData(Qt.ItemDataRole.UserRole,record[5]);self.result_table.setItem(row,col,item)
    def open_result(self,row):
        item=self.result_table.item(row,0);index=item.data(Qt.ItemDataRole.UserRole)
        if index is None:raise ValueError('This point failed before a usable geometry was saved. It is retained as a missing point.')
        calc=calculation_page(self.store,self.selected_job(),indices=[index]);self.window.add_document(calc);self.window.activate_calculation(calc);self.showMinimized()
    def inspect_frame(self):
        ident=self.selected_job();index=self.page_start.value()-1
        calc=self.window.calculation
        if calc and calc.metadata.get('mlip_job')==ident:index=calc.metadata['mlip_frames'][self.window.step]
        frame=self.store.get_frame(ident,index);s=self.store.job(ident)['input']['structure']
        dialog=QDialog(self);dialog.setWindowTitle(f'Saved frame {index+1} · full per-atom forces');dialog.resize(850,550)
        layout=QVBoxLayout(dialog);layout.addWidget(note('Forces: eV/Å; velocities: Å/fs; masses: amu. Energies in job records are eV.'))
        table=QTableWidget(len(s['numbers']),6);table.setHorizontalHeaderLabels(['Atom','Identity','Mass','Position / Å','Force / eV Å⁻¹','Velocity / Å fs⁻¹']);table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for i,z in enumerate(s['numbers']):
            values=[f'{ELEMENTS[z]}{i+1}',s['ids'][i],frame['masses'][i],frame['positions'][i],frame['forces'][i],frame.get('velocities',[None]*len(s['numbers']))[i]]
            for j,value in enumerate(values):table.setItem(i,j,QTableWidgetItem(str(value)))
        layout.addWidget(table);self.frame_dialog=dialog;dialog.show()
    def cancel_job(self):self.manager.cancel(self.selected_job())
    def open_page(self):
        calc=calculation_page(self.store,self.selected_job(),self.page_start.value()-1,self.page_count.value())
        self.window.add_document(calc);self.window.activate_calculation(calc,0);self.showMinimized()
    def open_final_points(self):
        ident=self.selected_job();indices=[]
        for name in ('neb','scan','conformers'):
            result=self.store.artifact(ident,name)
            if not result:continue
            rows=result['history'][-1]['images'] if name=='neb' else result['points'] if name=='scan' else result['retained']
            indices=[r['frame'] for r in rows if r['frame'] is not None];break
        if not indices:raise ValueError('Choose a NEB, scan, or conformer job with saved result points.')
        calc=calculation_page(self.store,ident,indices=indices);self.window.add_document(calc);self.window.activate_calculation(calc);self.showMinimized()
    def plot_md(self):
        ident=self.selected_job();rows=[r for _,r in self.store.frames(ident,self.page_start.value()-1,self.page_count.value()) if 'time' in r]
        if not rows:raise ValueError('Select an MD job/page first.')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        dialog=QDialog(self);dialog.setWindowTitle('MD diagnostics · selected saved page');dialog.resize(800,580);layout=QVBoxLayout(dialog)
        fig=Figure();canvas=FigureCanvasQTAgg(fig);layout.addWidget(canvas);energy,temp=fig.subplots(2,1,sharex=True)
        for key,label in [('energy','Potential'),('kinetic_energy','Kinetic'),('total_energy','Total')]:
            # Plot changes to keep large electronic reference energies readable.
            values=np.array([r[key] for r in rows]);energy.plot([r['time'] for r in rows],values-values[0],label=label)
        energy.set_ylabel('Energy change / eV');energy.legend();temp.plot([r['time'] for r in rows],[r['temperature'] for r in rows]);temp.set_ylabel('Temperature / K');temp.set_xlabel('Time / fs');fig.tight_layout();canvas.draw()
        layout.addWidget(note('Changes are relative to the first frame of this bounded page. Absolute energies are retained in each saved frame; NVT total energy is not conserved.'))
        self.md_dialog=dialog;dialog.show()
    def seed_child(self):
        ident=self.selected_job();calc=self.window.calculation
        if not calc or calc.metadata.get('mlip_job')!=ident:raise ValueError('Open this job’s saved page and select the desired frame/image first.')
        index=calc.metadata['mlip_frames'][self.window.step]
        self.seed(ident,index,self.next_job.currentData())
    def seed(self,ident,index,kind):
        data=self.store.job(ident)['input'];frame=self.store.get_frame(ident,index)
        self.structure=deepcopy(data['structure']);self.structure['positions']=frame['positions'];self.structure.pop('velocities',None)
        m=data['model'];self.backend.setCurrentText(m['backend']);self.checkpoint.setCurrentText(m.get('checkpoint',''));self.device.setCurrentText(m['device']);self.precision.setCurrentText(m['precision']);self.task.setText(m.get('task') or '');self.head.setText(m.get('head') or '');self.ack.setChecked(m.get('domain_ack',False));self.local.setText(m.get('local_file',''));self.manifest.setPlainText(json.dumps(m.get('manifest',{}),indent=2))
        self.parent_job={'job':ident,'frame':index};self.charge.setValue(self.structure['charge']);self.mult.setValue(self.structure['multiplicity'])
        self.input_label.setText(f'Child of {ident[:8]}, saved frame {index+1}. Model and numerical settings remain editable.');self.job.setCurrentIndex(self.job.findData(kind));self.tabs.setCurrentIndex(0)
    def restart_geometry(self):
        ident=self.selected_job();n=self.store.count(ident)
        if not n:raise ValueError('No saved geometry to restart.')
        self.seed(ident,n-1,self.store.job(ident)['input']['kind'])
    def continue_md(self):
        ident=self.selected_job();job=self.store.job(ident);data=deepcopy(job['input']);cp=self.store.artifact(ident,'checkpoint')
        if job['status'] not in ('completed','cancelled','failed','interrupted') or data['kind']!='md' or not cp or not cp['exact']:raise ValueError('Select a stopped MD job with an exact saved checkpoint.')
        data['parent']={'job':ident,'frame':cp['frame']};data['continuation']={'job':ident,'input_hash':job['input_hash']}
        child=self.store.submit(data);self.refresh_jobs();self.select_job(child)
    def compare_results(self):
        ident=self.selected_job();conf=self.store.artifact(ident,'conformers');irc=self.store.artifact(ident,'irc');indices=[]
        if conf:indices=[r['frame'] for r in conf['retained']]
        elif irc:
            for branch in irc['branches']:
                child=branch.get('endpoint_job');n=self.store.count(child) if child else 0
                calc=calculation_page(self.store,child,indices=[n-1]) if n else calculation_page(self.store,ident,indices=[branch['points'][-1]['frame']])
                self.window.add_document(calc)
        else:raise ValueError('Select a conformer search or an IRC with saved endpoints.')
        for index in indices:self.window.add_document(calculation_page(self.store,ident,indices=[index]))
        self.window.refresh_documents();self.window.inspector.setCurrentIndex(self.window.compare_tab);self.window.show_comparison();self.showMinimized()
    def open_folder(self):QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.root)))
    def export_frames(self):
        ident=self.selected_job();path,_=QFileDialog.getSaveFileName(self,'Export full saved trajectory','trajectory.extxyz','Extended XYZ (*.extxyz)')
        if not path:return
        # Streaming export is moved to a worker thread; each page is bounded.
        self.export_task=TrajectoryExport(self.store.path,ident,path,self);self.export_task.failed.connect(lambda m:QMessageBox.warning(self,'Export failed',m))
        self.export_task.done.connect(lambda:QMessageBox.information(self,'Trajectory exported','Saved all available frames with eV energies, full forces and velocities.'))
        self.export_task.start()
    def make_environment(self):
        layout=self.page('Environment / models')
        offline=bundle_directory() is not None
        message=('MLIP Offline edition: CPU environments and public MACE-ANI-CC / AIMNet2 checkpoints are included. Setup unpacks them locally with automatic paths; no internet is needed. UMA and MACE-OFF23 weights are excluded and still require access/licence approval and an online download.' if offline else 'GUI edition: Python, calculator dependencies and public models download on first setup; paths are automatic. For a computer without internet, use the MLIP Offline edition. Cached models work offline.')
        layout.addWidget(note(message+' Allow several GB of disk space per calculator. Use Guided setup to choose models and detect this computer’s CPU/GPU.'))
        self.setup_target=note('');layout.addWidget(self.setup_target)
        row=QHBoxLayout();self.auto_button=button('Guided setup — add models / enable GPU / repair…',lambda:self.safe(self.guided_setup));self.auto_button.setObjectName('primary');row.addWidget(self.auto_button)
        self.stop_setup_button=button('Stop setup',self.stop_setup);self.stop_setup_button.setEnabled(False);row.addWidget(self.stop_setup_button);layout.addLayout(row)
        self.readiness=note('Ready to set up. No system Python, terminal or manually entered paths are needed.');layout.addWidget(self.readiness)
        self.setup_log=QPlainTextEdit();self.setup_log.setReadOnly(True);self.setup_log.setMaximumBlockCount(1000);layout.addWidget(self.setup_log)
        row=QHBoxLayout();row.addWidget(button('Open setup folder',self.open_folder))
        advanced=button('Advanced setup…',lambda:self.advanced_environment.setVisible(not self.advanced_environment.isVisible()));row.addWidget(advanced);layout.addLayout(row)
        self.advanced_environment=QGroupBox('Existing environments and individual setup steps');extra=QVBoxLayout(self.advanced_environment);layout.addWidget(self.advanced_environment)
        self.environment_path=QLineEdit(self.manager.python(self.backend.currentText()));self.environment_path.setAccessibleName('Calculation Python (advanced)');extra.addWidget(self.environment_path)
        extra.addWidget(button('Set up selected checkpoint (advanced)',lambda:self.safe(self.automatic_setup)))
        row=QHBoxLayout();row.addWidget(button('Connect existing Python…',self.choose_python));row.addWidget(button('Create CPU environment',lambda:self.safe(self.setup_environment)));row.addWidget(button('Check environment',lambda:self.safe(self.probe_environment)));extra.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Connect Hugging Face',lambda:self.safe(self.huggingface_login)));row.addWidget(button('Open UMA access page',lambda:QDesktopServices.openUrl(QUrl('https://huggingface.co/facebook/UMA'))));extra.addLayout(row)
        self.license_ack=QCheckBox('I have access and accept the selected checkpoint’s licence shown on Calculation.');extra.addWidget(self.license_ack)
        row=QHBoxLayout();row.addWidget(button('Download selected model',lambda:self.safe(lambda:self.model_action('download'))));row.addWidget(button('Check selected model',lambda:self.safe(lambda:self.model_action('check'))));extra.addLayout(row)
        self.advanced_environment.hide()
        layout.addWidget(note('Use Guided setup to detect this computer and install or repair CPU/GPU support. CUDA requires an NVIDIA GPU and a working driver. Model access and licences remain the owner’s requirements. Setup never queues a calculation automatically.'))
    def guided_setup(self):
        if self.setup_busy():raise ValueError('Wait for the current setup operation to finish.')
        from .setup_ui import SetupWizard
        SetupWizard(self,self.manager).exec()
        self.check_results.clear();self.backend_changed()
    def setup_busy(self):
        return self.automatic or bool(self.control_process) or bool(self.setup_task and self.setup_task.isRunning())
    def update_setup_controls(self):
        busy=self.setup_busy()
        self.tabs.widget(0).setEnabled(not busy);self.tabs.widget(1).setEnabled(not busy)
        self.advanced_environment.setEnabled(not busy);self.auto_button.setEnabled(not busy)
        self.stop_setup_button.setEnabled(busy and not self.setup_cancelled)
    def lock_setup(self):
        if not self.manager.owns_queue:raise ValueError('Set up models in the first open Alder window.')
        if any(j['status']=='running' for j in self.store.jobs()):raise ValueError('Wait for the active calculation to finish before changing its environment.')
        if not self.setup_lock.tryLock(0):raise ValueError('Another window is setting up models. Wait for it to finish.')
        self.manager.preparing=self.backend.currentText()
    def finish_setup(self,message):
        self.automatic=False;self.manager.preparing=None;self.setup_lock.unlock()
        self.readiness.setText(message);self.setup_log.appendPlainText(message);self.update_setup_controls()
    def automatic_setup(self):
        if self.setup_busy():raise ValueError('A setup operation is already running.')
        self.model_config()  # Validate local manifest before downloading packages.
        self.lock_setup();self.automatic=True;self.setup_cancelled=False;self.install_attempted=False
        self.tabs.setCurrentIndex(2);self.update_setup_controls()
        self.setup_log.appendPlainText('Setting up '+self.checkpoint.currentText()+'…')
        python=self.manager.python(self.backend.currentText()) or str(managed_python(self.manager.root,self.backend.currentText()))
        self.environment_path.setText(python)
        try:
            if Path(python).is_file():self.probe_environment(self.automatic_probed)
            else:self.setup_environment(self.automatic_probed)
        except Exception as error:self.finish_setup('Setup failed: '+redact(error))
    def automatic_probed(self,result):
        if result.get('error') or not result.get('ready'):
            managed=str(managed_python(self.manager.root,self.backend.currentText()))
            if not self.install_attempted and self.environment_path.text()==managed:
                self.setup_environment(self.automatic_probed);return
            self.finish_setup('Environment unavailable: '+result.get('error','; '.join(result.get('errors',[])))+' Use Guided setup to repair CPU/GPU support, or connect an existing environment in Advanced setup.');return
        if self.device.currentText() not in result['devices']:
            self.finish_setup('Selected device is unavailable. Use Guided setup to install or repair GPU support, or choose CPU on Calculation.');return
        self.model_action('availability',self.automatic_available)
    def automatic_available(self,result):
        if result.get('error'):
            self.finish_setup('Setup failed: '+result['error']);return
        if result.get('cached'):
            self.model_action('check',self.automatic_checked);return
        if result.get('licensed') and not self.license_ack.isChecked():
            spec=specification(self.model_config())
            prompt=QMessageBox(self);prompt.setWindowTitle('Model access and licence');prompt.setText(spec['name']+' requires your acknowledgement before download.')
            prompt.setInformativeText(spec['license']+'\n\nContinue only if you have the required access and accept these terms. You can cancel and set up a public checkpoint instead.')
            prompt.setStandardButtons(QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel);prompt.setDefaultButton(QMessageBox.StandardButton.Cancel)
            link=prompt.addButton('Open licence / access page',QMessageBox.ButtonRole.ActionRole)
            url='https://huggingface.co/facebook/UMA' if spec['backend']=='uma' else 'https://github.com/gabor1/ASL'
            link.clicked.connect(lambda:QDesktopServices.openUrl(QUrl(url)))
            if prompt.exec()!=QMessageBox.StandardButton.Yes:
                self.finish_setup('Setup pending model access/licence acknowledgement. Installed packages are retained.');return
            self.license_ack.setChecked(True)
        if result.get('authenticated') is False:
            self.huggingface_login(self.automatic_logged_in);return
        self.model_action('download',self.automatic_downloaded)
    def automatic_logged_in(self,result):
        if result.get('connected'):self.model_action('download',self.automatic_downloaded)
        else:self.finish_setup('Hugging Face connection pending: '+result.get('error','Login cancelled. Run setup again when ready.'))
    def automatic_downloaded(self,result):
        if result.get('error'):
            message='Download failed: '+result['error']
            if self.backend.currentText()=='uma':message+=' Check that your Hugging Face account has UMA access and the read token allows this repository. Use Advanced setup to reconnect, then retry.'
            self.finish_setup(message);return
        self.model_action('check',self.automatic_checked)
    def automatic_checked(self,result):
        if not result.get('ready'):
            self.finish_setup('Model check failed: '+result.get('error','No readiness result.'));return
        backend=self.backend.currentText();cfg=self.manager.config[backend]
        cfg['last_ready_model']={k:v for k,v in self.model_config().items() if k!='domain_ack'};self.manager.persist()
        message=self.checkpoint.currentText()+' is ready on '+self.device.currentText()+'. Return to Calculation to capture a structure and queue a job.'
        if not cfg['probe'].get('sella'):message+=' TS/IRC remain unavailable: Sella did not pass its import check. See the setup log.'
        self.finish_setup(message)
    def stop_setup(self):
        self.setup_cancelled=True;self.stop_setup_button.setEnabled(False)
        if self.setup_task and self.setup_task.isRunning():
            self.setup_task.requestInterruption();self.readiness.setText('Stopping after the current installer operation. Completed steps will be reused on retry.')
        elif self.control_process:
            self.readiness.setText('Stopping setup…');self.control_process.kill()
        elif self.automatic:self.finish_setup('Setup stopped. Run setup again to continue.')
    def choose_python(self):
        path,_=QFileDialog.getOpenFileName(self,'Select calculation environment Python','','Python executable (python python3 python.exe);;All files (*)')
        if path:self.environment_path.setText(path);self.safe(self.probe_environment)
    def setup_environment(self,callback=None):
        if (self.setup_task and self.setup_task.isRunning()) or self.control_process:raise ValueError('A setup operation is already running.')
        if not self.automatic:self.lock_setup();self.setup_cancelled=False
        self.install_attempted=True
        backend=self.backend.currentText();task=SetupTask(self.manager.root,backend,self);self.setup_task=task
        task.message.connect(self.setup_log.appendPlainText)
        # Wait for QThread.finished before exposing a retry or starting the next step.
        outcome={};task.done.connect(lambda path:outcome.update(path=path));task.failed.connect(lambda error:outcome.update(error=error))
        def finished():
            self.setup_task=None;task.deleteLater()
            if not self.automatic:self.manager.preparing=None;self.setup_lock.unlock()
            if self.setup_cancelled:self.finish_setup('Setup stopped. Completed installation steps are retained.');return
            if outcome.get('error'):self.finish_setup('Setup failed: '+outcome['error']);return
            path=outcome['path'];self.manager.config.setdefault(backend,{})['python']=path;self.manager.persist();self.environment_path.setText(path)
            try:self.probe_environment(callback)
            except Exception as error:self.finish_setup('Setup failed: '+redact(error))
        task.finished.connect(finished);task.start();self.update_setup_controls();self.readiness.setText('Installing the calculation environment. This can take several minutes…')
    def control(self,action,args,callback,secret=None):
        if self.control_process:raise ValueError('A setup/check operation is already running.')
        python=self.environment_path.text().strip()
        if not Path(python).is_file():raise ValueError('Use Set up selected model first, or connect an existing Python under Advanced setup.')
        if not self.automatic:self.setup_cancelled=False
        result=self.manager.root/'check-result.json';result.unlink(missing_ok=True)
        self.control_process=QProcess(self);p=self.control_process;p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        p.readyReadStandardOutput.connect(lambda:self.setup_log.appendPlainText(redact(bytes(p.readAllStandardOutput()).decode('utf-8','replace'))))
        def finished(code,status):
            if self.control_process is not p:return
            # Release this process BEFORE the callback starts the next setup step.
            self.control_process=None;p.deleteLater()
            try:
                if self.setup_cancelled:self.finish_setup('Setup stopped. Completed downloads and installation steps are retained.');return
                value=json.loads(result.read_text()) if result.exists() else {'error':'Worker exited without a result. Check the environment and setup log.'}
                if code and not value.get('error'):value={'error':'Worker exited unsuccessfully. Check the setup log.'}
                if value.get('error'):self.readiness.setText(value['error'])
                callback(value)
            except Exception as error:
                if self.automatic:self.finish_setup('Setup failed: '+redact(error))
                else:self.readiness.setText(redact(error))
            finally:self.update_setup_controls()
        p.finished.connect(finished)
        p.errorOccurred.connect(lambda e:finished(-1,None) if e==QProcess.ProcessError.FailedToStart else None)
        if secret is not None:p.started.connect(lambda:(p.write((secret+'\n').encode()),p.closeWriteChannel()))
        self.readiness.setText({'probe':'Checking installed dependencies and devices…','availability':'Checking cached weights and access requirements…','login':'Connecting Hugging Face…','download':'Downloading the selected checkpoint…','check':'Running a real energy/force readiness calculation…'}[action])
        self.setup_log.appendPlainText(self.readiness.text());self.update_setup_controls()
        start_external(p,python,[self.manager.worker(),action,'--result',str(result),*args])
    def probe_environment(self,callback=None):
        backend=self.backend.currentText();python=self.environment_path.text().strip();device=self.device.currentText()
        def done(result):
            self.check_results.clear()
            self.manager.config.setdefault(backend,{}).update(python=python,probe=result);self.manager.persist()
            self.device.clear();self.device.addItems(result.get('devices',[]))
            if device in result.get('devices',[]):self.device.setCurrentText(device)
            elif device:self.device.setCurrentIndex(-1)
            self.readiness.setText(json.dumps(result,indent=2))
            if callback:callback(result)
        self.control('probe',['--backend',backend],done)
    def huggingface_login(self,callback=None):
        if not Path(self.environment_path.text().strip()).is_file():raise ValueError('Use Set up selected model to install its environment before connecting Hugging Face.')
        dialog=QDialog(self);dialog.setWindowTitle('Connect Hugging Face');layout=QVBoxLayout(dialog)
        layout.addWidget(note('UMA requires an approved Hugging Face account. Create a read token with access to facebook/UMA, then paste it below. The official client saves it locally; it is never written to jobs or setup logs.'))
        row=QHBoxLayout();row.addWidget(button('Open UMA access page',lambda:QDesktopServices.openUrl(QUrl('https://huggingface.co/facebook/UMA'))));row.addWidget(button('Create read token',lambda:QDesktopServices.openUrl(QUrl('https://huggingface.co/settings/tokens'))));layout.addLayout(row)
        token=QLineEdit();token.setEchoMode(QLineEdit.EchoMode.Password);token.setAccessibleName('Hugging Face read token');layout.addWidget(token)
        row=QHBoxLayout();connect=button('Connect',dialog.accept);connect.setEnabled(False);token.textChanged.connect(lambda text:connect.setEnabled(bool(text.strip())))
        row.addWidget(connect);row.addWidget(button('Cancel',dialog.reject));layout.addLayout(row)
        accepted=dialog.exec()==QDialog.DialogCode.Accepted;secret=token.text().strip();token.clear();dialog.deleteLater()
        done=callback or (lambda r:self.readiness.setText('Hugging Face connected.' if r.get('connected') else r.get('error','Connection failed.')))
        if accepted and secret:self.control('login',[],done,secret=secret)
        elif callback:callback({'connected':False,'error':'Login cancelled. Run setup again when ready.'})
    def model_action(self,action,callback=None,*,config=None,structure=None):
        config=self.model_config() if config is None else deepcopy(config)
        path=self.manager.root/'model-check.json';atomic_json(path,config)
        key=self.model_key(config)
        if action=='check':self.check_results.pop(key,None)
        def done(result):
            if action=='check' and result.get('ready'):self.check_results[key]=result
            self.readiness.setText(json.dumps(result,indent=2))
            if callback:callback(result)
        args=['--config',str(path),'--cache',str(self.manager.root/'models')]
        bundle=bundle_directory()
        if action=='download' and bundle is not None:args+=['--bundled-cache',str(bundle/'models')]
        if action=='check' and (structure is not None or self.structure is not None):
            if structure is None:
                structure=deepcopy(self.structure);structure.update(charge=self.charge.value(),multiplicity=self.mult.value())
            sample=self.manager.root/'readiness-structure.json';atomic_json(sample,structure);args+=['--structure',str(sample)]
        if action=='download' and self.license_ack.isChecked():args.append('--licensed')
        self.control(action,args,done)
    def closeEvent(self,event):
        if (self.setup_task and self.setup_task.isRunning()) or self.control_process or (hasattr(self,'export_task') and self.export_task.isRunning()):
            event.ignore();self.showMinimized();return
        event.accept()


class TrajectoryExport(QThread):
    done=Signal();failed=Signal(str)
    def __init__(self,db,ident,path,parent):super().__init__(parent);self.db=db;self.ident=ident;self.path=Path(path)
    def run(self):
        from ase import Atoms, units
        from ase.calculators.singlepoint import SinglePointCalculator
        from ase.io import write
        store=Store(self.db);temp=self.path.with_suffix(self.path.suffix+'.part')
        try:
            data=store.job(self.ident)['input'];s=data['structure']
            with temp.open('w',encoding='utf-8') as out:
                for start in range(0,store.count(self.ident),100):
                    for index,row in store.frames(self.ident,start,100):
                        a=Atoms(numbers=s['numbers'],positions=row['positions'],masses=row['masses'],cell=row['cell'],pbc=row['pbc'])
                        a.info.update(charge=s['charge'],multiplicity=s['multiplicity'],job=self.ident,frame=index,energy_unit='eV',velocity_unit='angstrom/fs')
                        a.arrays['atom_id']=np.array(s['ids'])
                        if 'velocities' in row:a.arrays['velocity']=np.array(row['velocities'])
                        a.calc=SinglePointCalculator(a,energy=row['energy'],forces=np.array(row['forces']))
                        write(out,a,format='extxyz')
            os.replace(temp,self.path);atomic_json(self.path.with_suffix('.provenance.json'),dict(input=data,provenance=store.artifact(self.ident,'provenance')));self.done.emit()
        except Exception as error:self.failed.emit(redact(error))
        finally:store.close();temp.unlink(missing_ok=True)


def open_mlip(window):
    dialog=getattr(window,'mlip_dialog',None)
    if dialog is None:window.mlip_dialog=dialog=MLIPDialog(window)
    dialog.showNormal();dialog.raise_();dialog.activateWindow()
    if dialog.structure is None:
        try:dialog.capture_input()
        except ValueError:pass
