"""Numerical correctness and saved-file contracts for comparison, inputs, and MLIP jobs."""
from pathlib import Path
import numpy as np
import pytest
from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from ase.io.extxyz import write_extxyz
from ase.io.trajectory import Trajectory
from ase.units import Hartree

from alder.alignment import atom_pairs, rigid_fit
from alder.trajectory import read_trajectory
from alder.job_setup import generate_input, scan_coordinates


def test_alignment_rotation_mapping_and_chirality():
    reference = np.array([[0.,0,0],[1,0,0],[0,2,0],[0,0,3]])
    rotation = np.array([[0,-1.,0],[1,0,0],[0,0,1]])
    moving = reference @ rotation + [3,4,-1]
    r,t,rmsd = rigid_fit(moving,reference)
    np.testing.assert_allclose(moving@r+t,reference,atol=1e-14)
    assert rmsd < 1e-14 and np.linalg.det(r)>0.999
    reflected = reference.copy(); reflected[:,0] *= -1
    assert rigid_fit(reflected,reference)[2] > 0.5
    a,b = atom_pairs(np.array([6,1,8,7]),np.array([7,8,6]),mapping='1:3, 3:2, 4:1')
    assert a.tolist()==[0,2,3] and b.tolist()==[2,1,0]
    a,b = atom_pairs(np.array([6,1,8,7]),np.array([6,8,7]),heavy=True)
    assert a.tolist()==[0,2,3] and b.tolist()==[0,1,2]
    for mapping in ['', '1:1, 1:2', '0:1', '1:99', '1:1']:
        with pytest.raises(ValueError):
            atom_pairs(np.array([6,8]),np.array([8,6]),heavy=False,mapping=mapping)


def test_ase_sella_saved_results_and_geometric_units(tmp_path):
    frames = []
    for shift in [0.,0.1]:
        atoms = Atoms('OH2',positions=[[0,0,0],[0.97+shift,0,0],[-.24,.94,0]])
        atoms.calc = SinglePointCalculator(atoms,energy=(-1+shift)*Hartree,forces=np.ones((3,3))*.1)
        frames.append(atoms)
    for suffix in ['traj','extxyz']:
        path = tmp_path/f'sella.{suffix}'
        if suffix=='traj':
            with Trajectory(str(path),'w') as writer:
                for atoms in frames:
                    writer.write(atoms)
        else:
            with path.open('w') as writer:
                write_extxyz(writer,frames)
        calculation = read_trajectory(path)
        np.testing.assert_allclose(calculation.energies,[-1,-.9],atol=1e-10)
        np.testing.assert_allclose(calculation.coords,[f.positions for f in frames],atol=1e-8)
        assert calculation.atomnos.tolist()==[8,1,1]
        assert calculation.metadata['max_forces'][0]==pytest.approx(np.sqrt(.03))
        path.unlink()  # The reader releases file handles (also exercised on Windows).
    path = tmp_path/'optim.xyz'
    path.write_text('2\nIteration 0 Energy -40.12345678\nC 0 0 0\nH 1.09 0 0\n2\nIteration 1 Energy -40.23456789\nC 0 0 0\nH 1.08 0 0\n')
    calc = read_trajectory(path)
    np.testing.assert_allclose(calc.energies,[-40.12345678,-40.23456789])
    assert calc.summary['Program']=='geomeTRIC'
    path.write_text('1\nenergy=-12.5\nH 0 0 0\n')
    assert np.isnan(read_trajectory(path).energies[0])  # Plain XYZ has no implied units.
    path.write_text('1\nEnergy=-27.211386245988 eV\nH 0 0 0\n')
    assert read_trajectory(path).energies[0]==pytest.approx(-1,abs=1e-7)
    path.write_text('1\n\nH 0 0 0\n1\n\nO 0 0 0\n')
    with pytest.raises(ValueError,match='same elements'):
        read_trajectory(path)
    path.write_text('2\n\nH 0 0 0\n')
    with pytest.raises(ValueError):
        read_trajectory(path)


def test_gaussian_orca_setup_validation_and_scan_indices():
    atomnos = [8,1,1]
    coords = [[0,0,0],[.97,0,0],[-.24,.94,0]]
    for engine in ['Gaussian','ORCA']:
        for job in ['sp','opt','optfreq','freq','ts','irc','scan','td']:
            options = dict(engine=engine,job=job,method='PBE0',basis='def2-SVP',cores=4,memory=8,
                           scan='B 1 2 10 0.1\nA 2 1 3 2 -2',solvation='SMD',solvent='Water',roots=6,tda=True)
            text = generate_input(atomnos,coords,options)
            assert '0.9700000000' in text and '0 1' in text
            if engine=='Gaussian':
                assert 'PBE1PBE/Def2SVP' in text and '%mem=8GB' in text and 'SCRF=(SMD,Solvent=Water)' in text
                if job=='scan': assert 'B 1 2 S 10 0.1' in text
                if job=='td': assert 'TDA=(NStates=6)' in text
            else:
                assert '%maxcore 1638' in text and '%pal nprocs 4 end' in text
                if job=='scan': assert 'B 0 1 = 0.97000000, 1.97000000, 11' in text
                if job=='td': assert 'NRoots 6\n  TDA true' in text
    with pytest.raises(ValueError,match='electron count'):
        generate_input(atomnos,coords,dict(engine='ORCA',job='sp',multiplicity=2))
    assert 'NumFreq' in generate_input(atomnos,coords,dict(engine='ORCA',job='freq',method='MP2'))
    with pytest.raises(ValueError,match='DFT or HF'):
        generate_input(atomnos,coords,dict(engine='ORCA',job='td',method='MP2'))
    with pytest.raises(ValueError,match='Increase total memory'):
        generate_input(atomnos,coords,dict(engine='ORCA',job='sp',cores=1024,memory=1))
    with pytest.raises(ValueError,match='Scan atom numbers'):
        scan_coordinates('B 1 4 10 .1',coords)
    with pytest.raises(ValueError,match='positive'):
        scan_coordinates('B 1 2 10 -.1',coords)
    with pytest.raises(ValueError,match='collinear'):
        scan_coordinates('D 1 2 3 4 10 1',[[0,0,0],[1,0,0],[2,0,0],[3,0,0]])
