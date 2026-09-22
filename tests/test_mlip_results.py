import numpy as np
import pytest
from ase import Atoms, units
from ase.constraints import FixAtoms
from ase.io import write
from molecule_studio.mlip.contract import snapshot
from molecule_studio.mlip.store import Store
from molecule_studio.mlip_results import calculation_page
from molecule_studio.trajectory import read_trajectory


def test_bounded_result_units_modes_and_path_associations(tmp_path):
    store=Store(tmp_path/'jobs.sqlite')
    data=snapshot(dict(numbers=[1,1],positions=[[0,0,0],[1,0,0]],charge=0,multiplicity=1),{},'sp')
    ident=store.submit(data)
    for i in range(4):
        store.frame(ident,dict(positions=[[0,0,0],[1+i*.1,0,0]],energy=(i+1)*units.Hartree,
            forces=[[1,0,0],[-1,0,0]],max_force=1.,projected_max_force=1.,masses=[1.,1.],cell=np.zeros((3,3)).tolist(),pbc=[False]*3))
    store.artifact(ident,'frequencies',dict(frequencies=[-100.],modes=[[[1,0,0],[-1,0,0]]],positions=data['structure']['positions'],partial=False))
    store.artifact(ident,'scan',dict(axes=[dict(kind='bond',atoms=[0,1])],points=[
        dict(targets=[1.],energy=units.Hartree,frame=0),dict(targets=[1.1],energy=2*units.Hartree,frame=1),dict(targets=[1.2],energy=None,frame=None)]))
    calc=calculation_page(store,ident,1,2)
    np.testing.assert_allclose(calc.energies,[2,3])
    assert calc.metadata['mlip_frames']==[1,2]
    assert calc.metadata['mlip_rows'][0]['forces']==[[1,0,0],[-1,0,0]]
    assert np.isnan(calc.ir_intensities).all() and np.isnan(calc.raman_activities).all()
    assert calc.frequencies.tolist()==[-100.]
    assert calc.reaction_path.steps.tolist()==[-1,0,-1]
    assert np.isnan(calc.reaction_path.energies[-1])
    with pytest.raises(ValueError):calculation_page(store,ident,limit=1001)


def test_imported_simulation_input_preserved(tmp_path):
    a=Atoms('OH',positions=[[0,0,0],[.97,0,0]],masses=[18.,2.],cell=np.eye(3)*10,pbc=[True,False,False])
    a.info.update(charge=0,multiplicity=2);a.set_velocities([[.01,0,0],[-.02,0,0]])
    a.set_constraint(FixAtoms([0]));path=tmp_path/'input.traj';write(path,a)
    calc=read_trajectory(path);s=calc.metadata['simulation_frames'][0]
    np.testing.assert_allclose(s['masses'],[18,2]);np.testing.assert_allclose(s['cell'],a.cell)
    np.testing.assert_allclose(s['velocities'],a.get_velocities()*units.fs)
    assert s['pbc'].tolist()==[True,False,False] and s['multiplicity']==2
    assert s['ase_constraints'][0]['kwargs']['indices']==[0]
    with pytest.raises(ValueError,match='periodic'):
        snapshot(dict(numbers=[8,1],positions=a.positions.tolist(),charge=0,multiplicity=2,pbc=s['pbc'].tolist()),{},'sp')


def test_queue_recovers_worker_that_exits_after_startup(tmp_path,monkeypatch):
    from PySide6.QtCore import QCoreApplication, QObject
    from molecule_studio import mlip_ui
    app=QCoreApplication.instance() or QCoreApplication([])
    owner=QObject();root=tmp_path/'queue'
    manager=mlip_ui.JobManager(owner,root)
    data=snapshot(dict(numbers=[1,1],positions=[[0,0,0],[1,0,0]],charge=0,multiplicity=1),{},'sp')
    ident=manager.store.submit(data);assert manager.store.claim(ident)
    manager.store.artifact(ident,'worker',{'pid':12345});manager.shutdown()
    monkeypatch.setattr(mlip_ui,'process_alive',lambda _:True)
    restored=mlip_ui.JobManager(owner,root)
    try:
        assert restored.store.job(ident)['status']=='running'
        monkeypatch.setattr(mlip_ui,'process_alive',lambda _:False)
        restored.tick()
        assert restored.store.job(ident)['status']=='interrupted'
    finally:restored.shutdown()
