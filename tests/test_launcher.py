"""A Finder launch must retain diagnostics without a terminal."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from molecule_studio import launcher


@pytest.mark.parametrize('fails', [False, True])
def test_macos_frozen_startup_keeps_diagnostics(tmp_path, monkeypatch, fails):
    report = tmp_path / 'smoke.json'
    fake_sys = SimpleNamespace(platform='darwin', frozen=True, stderr=None, stdout=None,
                               argv=['MoleculeStudio', '--smoke-test', str(report), str(tmp_path)])
    monkeypatch.setattr(launcher, 'sys', fake_sys)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)

    def run(path, fixtures):
        assert path == report and fixtures == tmp_path
        if fails:
            raise RuntimeError('Test startup failure')
        return 0

    monkeypatch.setitem(sys.modules, 'molecule_studio.smoke', SimpleNamespace(run=run))
    try:
        assert launcher.main() == int(fails)
        log = (tmp_path / 'Library/Logs/Molecule Studio/studio.log').read_text(encoding='utf-8')
        assert 'Molecule Studio started' in log
        if fails:
            assert 'Test startup failure' in log
            assert json.loads(report.read_text())['ok'] is False
    finally:
        if fake_sys.stderr is not None:
            fake_sys.stderr.close()
