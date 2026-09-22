import pytest
from rdkit import Chem
from rdkit.Chem import rdDepictor
from molecule_studio.structure import layout_2d, embed_3d, molecule_from_model


def test_conversion_preserves_stereo_charge_isotope_and_planar_ring():
    for smiles in ('C[C@H](O)F', 'C[C@@H](O)F', '[13CH3][NH3+]', 'F/C=C/F', 'c1ccccc1'):
        mol=Chem.MolFromSmiles(smiles)
        rdDepictor.Compute2DCoords(mol)
        model,_=embed_3d(Chem.MolToMolBlock(mol))
        actual=Chem.RemoveHs(molecule_from_model(model))
        assert Chem.MolToSmiles(actual)==Chem.MolToSmiles(mol)
        roundtrip=Chem.MolFromMolBlock(layout_2d(model))
        assert Chem.MolToSmiles(roundtrip)==Chem.MolToSmiles(mol)
        if smiles=='c1ccccc1':
            import numpy as np
            p=np.array([[a[k] for k in 'xyz'] for a in model['atoms'] if a['el']=='C'])
            assert np.linalg.svd(p-p.mean(axis=0),compute_uv=False)[-1]<.01
    with pytest.raises(ValueError):embed_3d('broken')
    with pytest.raises(ValueError):embed_3d(Chem.MolToMolBlock(Chem.MolFromSmiles('*C')))
