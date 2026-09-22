"""Release check run by the actual executable, without Python on the PATH.

MoleculeStudio.exe --smoke-test report.json /path/to/tests/data
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

    def javascript(code):
        values = []
        window.web.page().runJavaScript(code, values.append)
        wait(lambda: bool(values))
        return values[0]

    try:
        wait(lambda: window.renderer_ready and window.builder_ready)
        assert not app.windowIcon().isNull()
        assert window.builder_fragment_preview.renderer.isValid()
        save('Qt WebEngine, WebChannel, SVG preview, and both local 3D views')
        with tempfile.TemporaryDirectory(prefix='Molecule Studio é ') as folder:
            folder = Path(folder)
            # Non-ASCII paths with spaces exercise installed/portable file handling.
            for name in ('gaussian-freq.log', 'orca6-opt.out'):
                source = folder / name
                shutil.copy2(fixtures / name, source)
                window.open_paths([source])
                wait(lambda: not window.busy)
                wait(lambda: javascript('window.sceneState.atoms') == len(window.calculation.atomnos))
                assert window.calculation.energies.size
                if name == 'gaussian-freq.log':
                    assert window.calculation.orbitals and window.calculation.frequencies.size
                save('Calculation import: ' + name)

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
