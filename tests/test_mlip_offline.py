"""Offline setup must fail closed and never fetch missing public bundle files."""
import json
from pathlib import Path
import zipfile
import pytest
from molecule_studio.mlip import environment, offline, registry


def test_local_model_copy_checks_digest_and_never_downloads(tmp_path,monkeypatch):
    source=tmp_path/'kit/models';cache=tmp_path/'cache';config={'backend':'mace','checkpoint':'MACE-ANI-CC'}
    spec=registry.CATALOGUE['MACE-ANI-CC'].copy()
    path=source/'mace/MACE-ANI-CC/weights.model';path.parent.mkdir(parents=True);path.write_bytes(b'public test weights')
    spec['sha256']=registry.checksum(path);monkeypatch.setitem(registry.CATALOGUE,spec['name'],spec)
    monkeypatch.setattr(environment.urllib.request,'urlopen',lambda *a,**k:pytest.fail('Network attempted'))
    result=environment.download(config,cache,bundled_cache=source)
    assert Path(result['path']).read_bytes()==path.read_bytes()
    assert result['sha256']==spec['sha256']
    Path(result['path']).unlink();path.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):environment.download(config,cache,bundled_cache=source)
    assert not Path(result['path']).exists()
    path.unlink()
    with pytest.raises(FileNotFoundError):environment.download(config,cache,bundled_cache=source)
    with pytest.raises(ValueError,match='acknowledgement'):
        environment.download({'backend':'uma','checkpoint':'uma-s-1p2'},cache,bundled_cache=source)


def test_bundle_integrity_paths_and_cancellation(tmp_path):
    archive=tmp_path/'python.zip'
    for name in ('../outside','C:/outside','/outside','..\\outside'):
        with zipfile.ZipFile(archive,'w') as z:z.writestr(name,'unsafe')
        with pytest.raises(ValueError,match='Unsafe'):offline.extract_python(archive,tmp_path/'runtime',lambda:False)
    with zipfile.ZipFile(archive,'w') as z:z.writestr('python.exe','runtime')
    with pytest.raises(InterruptedError):offline.extract_python(archive,tmp_path/'runtime',lambda:True)
    data={'files':{'python.zip':registry.checksum(archive)}}
    assert offline.verified_file(tmp_path,data,'python.zip')==archive
    archive.write_bytes(b'broken')
    with pytest.raises(ValueError,match='corrupt'):offline.verified_file(tmp_path,data,'python.zip')


def test_bundle_route_never_bootstraps_online(tmp_path,monkeypatch):
    monkeypatch.setenv('MOLECULE_STUDIO_OFFLINE_BUNDLE',str(tmp_path/'kit'))
    def install(directory,root,backend,emit,cancelled):
        assert directory==tmp_path/'kit' and backend=='aimnet2'
        raise ValueError('Offline kit unavailable')
    monkeypatch.setattr(offline,'install_environment',install)
    monkeypatch.setattr(environment.urllib.request,'urlopen',lambda *a,**k:pytest.fail('Network attempted'))
    with pytest.raises(ValueError,match='Offline kit unavailable'):environment.managed_environment(tmp_path/'runtime','aimnet2')
