"""Build the offline fragment library. Run with Studio's development Python."""
import json
from pathlib import Path
import sys
from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from molecule_studio.structure import embed_3d

# SMILES order defines the numbered atoms in both the diagram and the 3D model.
GROUPS = [
    ('Rings', 'Benzene', 'c1ccccc1', 0),
    ('Rings', 'Cyclopropane', 'C1CC1', 0),
    ('Rings', 'Cyclobutane', 'C1CCC1', 0),
    ('Rings', 'Cyclopentane', 'C1CCCC1', 0),
    ('Rings', 'Cyclohexane', 'C1CCCCC1', 0),
    ('Rings', 'Cycloheptane', 'C1CCCCCC1', 0),
    ('Rings', 'Cyclooctane', 'C1CCCCCCC1', 0),
    ('Rings', 'Cyclopentene', 'C1CC=CC1', 0),
    ('Rings', 'Cyclohexene', 'C1CCC=CC1', 0),
    ('Rings', 'Pyridine', 'c1ccncc1', 0),
    ('Rings', 'Pyrrole', 'c1cc[nH]c1', 0),
    ('Rings', 'Furan', 'c1ccoc1', 0),
    ('Rings', 'Thiophene', 'c1ccsc1', 0),
    ('Rings', 'Imidazole', 'c1ncc[nH]1', 0),
    ('Rings', 'Piperidine', 'N1CCCCC1', 0),
    ('Rings', 'Morpholine', 'O1CCNCC1', 3),
    ('Rings', 'Tetrahydrofuran', 'C1CCOC1', 0),
    ('Rings', 'Naphthalene', 'c1ccc2ccccc2c1', 0),
    ('Rings', 'Indole', 'c1ccc2[nH]ccc2c1', 0),
    ('Chains', 'Methyl', 'C', 0),
    ('Chains', 'Ethyl', 'CC', 0),
    ('Chains', 'Propyl', 'CCC', 0),
    ('Chains', 'Isopropyl', 'C(C)C', 0),
    ('Chains', 'tert-Butyl', 'C(C)(C)C', 0),
    ('Chains', 'Vinyl', 'C=C', 0),
    ('Chains', 'Ethynyl', 'C#C', 0),
    ('Functional groups', 'Hydroxyl', 'O', 0),
    ('Functional groups', 'Methoxy', 'OC', 0),
    ('Functional groups', 'Ethoxy', 'OCC', 0),
    ('Functional groups', 'Amino', 'N', 0),
    ('Functional groups', 'Dimethylamino', 'N(C)C', 0),
    ('Functional groups', 'Thiol', 'S', 0),
    ('Functional groups', 'Methylthio', 'SC', 0),
    ('Functional groups', 'Trifluoromethyl', 'C(F)(F)F', 0),
    ('Functional groups', 'Nitrile', 'C#N', 0),
    ('Carbonyl groups', 'Formyl', 'C=O', 0),
    ('Carbonyl groups', 'Acetyl', 'C(=O)C', 0),
    ('Carbonyl groups', 'Carboxylic acid', 'C(=O)O', 0),
    ('Carbonyl groups', 'Methyl ester · carbonyl side', 'C(=O)OC', 0),
    ('Carbonyl groups', 'Ethyl ester · carbonyl side', 'C(=O)OCC', 0),
    ('Carbonyl groups', 'Acetoxy ester · oxygen side', 'OC(=O)C', 0),
    ('Carbonyl groups', 'Amide · carbonyl side', 'C(=O)N', 0),
    ('Carbonyl groups', 'Acetamido · nitrogen side', 'NC(=O)C', 0),
    ('Functional groups', 'Nitro', '[N+](=O)[O-]', 0),
]


def build():
    library = []
    for category, name, smiles, root in GROUPS:
        mol = Chem.MolFromSmiles(smiles)
        rdDepictor.Compute2DCoords(mol)
        model, _ = embed_3d(Chem.MolToMolBlock(mol), name)
        drawer = rdMolDraw2D.MolDraw2DSVG(320, 160)
        options = drawer.drawOptions()
        options.padding = .15
        options.fixedFontSize = 14
        for atom in mol.GetAtoms():
            options.atomLabels[atom.GetIdx()] = f'{atom.GetSymbol()}{atom.GetIdx()+1}'
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        points = [[drawer.GetDrawCoords(i).x, drawer.GetDrawCoords(i).y] for i in range(mol.GetNumAtoms())]
        library.append(dict(name=name, category=category, smiles=smiles, root=root, model=model,
                            svg=drawer.GetDrawingText(), points=points))
    path = Path(__file__).resolve().parents[1] / 'src/molecule_studio/assets/fragments.json'
    path.write_text(json.dumps(library, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    print(f'Built {len(library)} offline fragments: {path}')


if __name__ == '__main__':
    build()
