"""Setup branches use real Qt process chaining; downloads/auth are simulated here."""
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest
from molecule_studio.mlip import environment


def test_availability_requires_no_network_for_public_or_cached_models(monkeypatch, tmp_path):
    config={'backend':'mace','checkpoint':'MACE-ANI-CC'}
    monkeypatch.setattr(environment.urllib.request,'urlopen',lambda *a,**k:pytest.fail('Unexpected network access'))
    assert environment.availability(config,tmp_path)=={'cached':False,'licensed':False}
    monkeypatch.setattr(environment,'model_path',lambda *a:(tmp_path/'weights',{'sha256':'a'*64}))
    assert environment.availability({'backend':'uma','checkpoint':'uma-s-1p2'},tmp_path)=={'cached':True,'sha256':'a'*64}


def test_availability_never_serializes_credentials_or_replaces_corruption(monkeypatch,tmp_path):
    monkeypatch.setitem(sys.modules,'huggingface_hub',SimpleNamespace(get_token=lambda:'hf_EXAMPLESECRET'))
    result=environment.availability({'backend':'uma','checkpoint':'uma-s-1p2'},tmp_path)
    assert result=={'cached':False,'licensed':True,'authenticated':True}
    assert 'SECRET' not in json.dumps(result)
    monkeypatch.setattr(environment,'model_path',lambda *a:(_ for _ in ()).throw(ValueError('checksum mismatch')))
    with pytest.raises(ValueError,match='checksum'):environment.availability({'backend':'mace','checkpoint':'MACE-ANI-CC'},tmp_path)


def test_managed_setup_honors_stop_before_bootstrap(tmp_path):
    with pytest.raises(InterruptedError):environment.managed_environment(tmp_path,'aimnet2',cancelled=lambda:True)
    assert not (tmp_path/'tools').exists()


def test_native_setup_flow_in_isolated_qt_process():
    # Other queue tests use QCoreApplication; widgets require a fresh QApplication.
    pytest.importorskip('PySide6')
    import subprocess
    path=Path(__file__).with_name('mlip_setup_smoke.py')
    result=subprocess.run([sys.executable,'-m','pytest',str(path),'-q','-p','no:cacheprovider'],
        env=os.environ|{'QT_QPA_PLATFORM':'offscreen'},capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
