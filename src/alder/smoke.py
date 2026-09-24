"""Release check run by the actual executable, without Python on the PATH.

Alder.exe --smoke-test report.json /path/to/tests/data
Only creates its report and temporary test files; does not save user settings.
"""
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
import traceback


def run(report_path, fixtures):
    report = {'ok': False, 'frozen': bool(getattr(sys, 'frozen', False)),
              'platform': platform.platform(), 'checks': []}

    def save(check=None):
        if check:
            report['checks'].append(check)
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    save()
    from PIL import Image
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    from .app import Window, configure_app

    class Offline(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, request):
            if request.requestUrl().scheme() in ('http', 'https'):
                request.block(True)

    app = QApplication([])
    configure_app(app)
    window = Window()
    errors = []
    warning = QMessageBox.warning
    QMessageBox.warning = lambda parent, title, message: errors.append(str(message))
    window.bridge.error.connect(errors.append)
    window.builder_bridge.error.connect(errors.append)
    window.builder_bridge.message.connect(lambda message, kind: errors.append(message) if kind == 'error' else None)
    window.sketch_bridge.message.connect(lambda message, kind: errors.append(message) if kind == 'error' else None)
    offline = Offline(window)
    profile = window.web.page().profile()
    profile.setUrlRequestInterceptor(offline)
    window.show()

    def wait(check, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            if errors:
                raise AssertionError(errors)
            if check():
                return
            time.sleep(.02)
        raise AssertionError('Timed out: ' + window.statusBar().currentMessage())

    def javascript(code, builder=False):
        values = []
        (window.builder_web if builder else window.web).page().runJavaScript(code, values.append)
        wait(lambda: bool(values))
        return values[0]

    try:
        wait(lambda: window.renderer_ready and window.builder_ready)
        assert not app.windowIcon().isNull()
        assert window.builder_fragment_preview.renderer.isValid()
        save('Qt WebEngine, WebChannel, SVG preview, and both local 3D views')
        with tempfile.TemporaryDirectory(prefix='Alder é ') as folder:
            folder = Path(folder)
            # Non-ASCII paths with spaces exercise installed/portable file handling.
            for name in ('gaussian-freq.log', 'orca6-opt.out', 'gaussian-td.log', 'orca6-adc2.out', 'gaussian-scan2d.log'):
                source = folder / name
                shutil.copy2(fixtures / name, source)
                window.open_paths([source])
                wait(lambda: not window.busy)
                wait(lambda: javascript('window.sceneState.atoms') == len(window.calculation.atomnos))
                assert window.calculation.energies.size
                if name == 'gaussian-freq.log':
                    assert window.calculation.orbitals and window.calculation.frequencies.size
                if name in ('gaussian-td.log', 'orca6-adc2.out'):
                    panel = window.uv_panel
                    assert panel.transitions and panel.table.rowCount() > 0
                    assert window.results.currentIndex() == window.uv_tab
                    panel.export('transitions', folder / 'uv.csv')
                    panel.export('curve', folder / 'uv-curve.csv')
                    panel.figure.savefig(folder / 'uv.png', dpi=200)
                    assert (folder / 'uv.csv').stat().st_size > 100
                    with Image.open(folder / 'uv.png') as image:
                        assert image.width > 200
                if name == 'gaussian-scan2d.log':
                    panel = window.path_panel
                    assert panel.table.rowCount() == 16 and panel.colorbar is not None
                    panel.table.selectRow(1)
                    assert window.step == 11
                    panel.export(folder / 'scan.csv')
                save('Calculation import: ' + name)

            # Exercise ASE's binary ULM reader in the frozen distribution too.
            from ase import Atoms
            from ase.calculators.singlepoint import SinglePointCalculator
            from ase.io.trajectory import Trajectory
            from .job_setup import generate_input
            saved = folder / 'sella.traj'
            with Trajectory(str(saved), 'w') as trajectory:
                for length in (.97, 1.02):
                    atoms = Atoms('OH2', positions=[[0,0,0],[length,0,0],[-.24,.94,0]])
                    atoms.calc = SinglePointCalculator(atoms, energy=-10-length)
                    trajectory.write(atoms)
            window.open_paths([saved])
            wait(lambda: not window.busy and window.calculation.name=='sella.traj')
            assert len(window.calculation.coords)==2
            assert window.calculation.energies[1]<window.calculation.energies[0]
            assert window.energy_profile_title.text()=='Potential energy'
            window.trajectory_speed.setValue(2)
            assert window.timer.interval()==175
            for engine in ('Gaussian','ORCA'):
                text = generate_input(window.calculation.atomnos, window.calculation.coords[-1], dict(engine=engine, job='optfreq'))
                assert '0 1' in text and 'Freq' in text
            save('ASE/Sella binary trajectory, saved energies, speed, Gaussian/ORCA input generation')
            window.open_paths([saved], compare=True)
            wait(lambda: not window.busy and window.comparison_active)
            reference = len(window.documents)-2
            window.compare_reference.setCurrentIndex(reference)
            for i in range(reference):
                window.compare_table.item(i,0).setCheckState(Qt.CheckState.Unchecked)
            wait(lambda: javascript('window.sceneState.structures')==2)
            assert window.comparison_results[-1][6]<1e-9
            assert javascript('new Set(calculationApp.view.model.atoms.map(a=>a.structureColor)).size')==2
            window.inspector.setCurrentIndex(0)
            save('Multi-document overlay, solid colors, rigid alignment and RMSD')

            xyz = folder / 'frames.xyz'
            xyz.write_text(window.calculation.xyz(0)+window.calculation.xyz(1), encoding='utf-8')
            window.open_paths([xyz])
            wait(lambda: not window.busy and window.calculation.name == 'frames.xyz')
            assert len(window.calculation.coords) == 2 and not window.builder_active
            xyz = folder / 'structure.xyz'
            xyz.write_text(window.calculation.xyz(0), encoding='utf-8')
            window.open_paths([xyz])
            wait(lambda: not window.busy and window.calculation.name == 'structure.xyz')
            assert len(window.calculation.coords) == 1 and not window.builder_active
            save('Single-frame and multi-frame XYZ viewing')

            window.inspector.setCurrentIndex(window.build_tab)
            window.builder_smiles.setText('CCO')
            window.builder_generate.click()
            wait(lambda: window.builder_state.get('atoms') == 9 and not window.builder_state.get('busy'))
            save('Bundled JavaScript RDKit/WASM SMILES to 3D, offline')
            window.builder_modes['2d'].click()
            wait(lambda: window.sketch_ready and not window.converting and
                 getattr(window, 'sketch_state', {}).get('atoms') == 3)
            save('Bundled Ketcher/Indigo 2D drawing, offline')
            window.builder_convert.click()
            wait(lambda: window.builder_mode == '3d' and not window.converting and
                 window.builder_model.get('embedding') == 'ETKDG + MMFF94' and
                 window.builder_state.get('atoms') == 9)
            save('Native RDKit ETKDG/MMFF 2D to 3D conversion')

            mol = folder / 'ethanol.mol'
            window.export_builder('mol', mol)
            wait(mol.exists)
            assert 'V2000' in mol.read_text(encoding='utf-8')
            window.builder_figure.click()
            wait(lambda: javascript('builderApp.editor.locked', True))
            javascript('builderApp.editor.selection=[0,1]', True)
            window.send(type='annotation', kind='dative')
            wait(lambda: any(b.get('kind') == 'dative' for b in window.builder_model['bonds']))
            assert len(window.builder_model['atoms']) == 9
            window.fog_enabled.setChecked(True)
            window.fog_strength.setValue(50)
            wait(lambda: javascript('!!builderApp.view.scene.fog', True))
            assert javascript("builderApp.view.color({el:'Au'})", True) == '#C5A148'
            save('Figure bond edits, shared fog and extended element colors')
            window.export_size.setValue(800)
            window.export_samples.setCurrentIndex(0)
            window.transparent.setChecked(True)
            png = folder / 'figure.png'
            window.render_export(png)
            wait(lambda: png.exists() and not window.exporting)
            with Image.open(png) as image:
                assert max(image.size) == 800 and image.mode == 'RGBA'
                assert image.getchannel('A').getextrema() == (0, 255)
            save('MOL and transparent PNG figure export')
            window.export_engine.setCurrentIndex(1)
            window.ray_samples.setValue(2)
            window.export_size.setMinimum(64)
            window.export_size.setValue(128)
            png = folder / 'raytraced.png'
            window.render_export(png)
            wait(lambda: png.exists() and not window.exporting, timeout=120)
            with Image.open(png) as image:
                assert max(image.size) == 128
                assert image.getchannel('A').getextrema() == (0, 255)
            save('Offline path-traced builder figure with fog and embedded BVH worker')
            window.open_paths([fixtures / 'gaussian-freq.log'])
            wait(lambda: not window.busy and window.calculation.name == 'gaussian-freq.log')
            window.results.setCurrentIndex(window.vibration_tab)
            window.vibration_table.selectRow(0)
            window.video_source.setCurrentIndex(2)
            window.video_period.setValue(8)
            window.video_cycles.setValue(1)
            window.video_size.addItem('64 px', 64)
            window.video_size.setCurrentIndex(window.video_size.count()-1)
            window.ray_samples.setValue(1)
            movie = folder / 'mode.webm'
            window.render_video(movie)
            wait(lambda: movie.exists() and not window.exporting, timeout=120)
            assert movie.read_bytes()[:4] == b'\x1aE\xdf\xa3'
            assert movie.stat().st_size > 300
            save('Offline path-traced normal-mode WebM with bundled video encoder')
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        save()
        profile.setUrlRequestInterceptor(None)
        window.close()
        app.processEvents()
        QMessageBox.warning = warning
    return 0 if report['ok'] else 1
