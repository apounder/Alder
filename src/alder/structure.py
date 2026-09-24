"""Local, stereochemistry-aware coordinate conversion for the desktop builder."""
from rdkit import Chem
from rdkit.Chem import AllChem, rdDepictor


def molecule_from_model(model):
    molecule = Chem.RWMol()
    for atom in model['atoms']:
        a = Chem.Atom(atom['el'])
        a.SetFormalCharge(atom.get('charge', 0))
        a.SetIsotope(atom.get('isotope', 0))
        a.SetNumRadicalElectrons(atom.get('radical', 0))
        molecule.AddAtom(a)
    orders = {1: Chem.BondType.SINGLE, 2: Chem.BondType.DOUBLE,
              3: Chem.BondType.TRIPLE, 4: Chem.BondType.AROMATIC}
    for bond in model['bonds']:
        if bond.get('kind') == 'ts':
            raise ValueError('TS contacts are 3D figure annotations. Remove them before generating a 2D chemical structure.')
        order = Chem.BondType.DATIVE if bond.get('kind') == 'dative' else orders[bond['order']]
        molecule.AddBond(bond['a'], bond['b'], order)
    molecule = molecule.GetMol()
    conf = Chem.Conformer(len(model['atoms']))
    conf.Set3D(True)
    for i, atom in enumerate(model['atoms']):
        conf.SetAtomPosition(i, (atom['x'], atom['y'], atom['z']))
    molecule.AddConformer(conf)
    Chem.SanitizeMol(molecule)
    Chem.AssignStereochemistryFrom3D(molecule)
    return molecule


def layout_2d(model):
    if not model['atoms']:
        return ''
    molecule = Chem.RemoveHs(molecule_from_model(model))
    rdDepictor.Compute2DCoords(molecule)
    return Chem.MolToMolBlock(molecule)


def embed_3d(block, name='Built molecule'):
    if len(block) > 2_000_000:
        raise ValueError('The sketch is too large to convert.')
    molecule = Chem.MolFromMolBlock(block, sanitize=True, removeHs=False)
    if molecule is None:
        raise ValueError('The sketch could not be converted. Check its bonds and valences.')
    if not molecule.GetNumAtoms():
        return {'name': name, 'smiles': '', 'atoms': [], 'bonds': []}, 'Empty structure'
    if any(a.HasQuery() or not a.GetAtomicNum() for a in molecule.GetAtoms()) or any(b.HasQuery() for b in molecule.GetBonds()):
        raise ValueError('Replace query atoms/bonds and R-groups with explicit elements before converting to 3D.')
    if molecule.GetNumHeavyAtoms() > 300:
        raise ValueError('2D-to-3D generation supports up to 300 heavy atoms. Import a 3D structure for larger systems.')
    molecule = Chem.AddHs(molecule)
    params = AllChem.ETKDGv3()
    params.randomSeed = 61453
    params.timeout = 15
    params.numThreads = 1
    params.enforceChirality = True
    if AllChem.EmbedMolecule(molecule, params) != 0:
        raise ValueError('Could not generate a 3D conformer. The 2D sketch and previous 3D structure are preserved.')
    method = 'ETKDG'
    converged = True
    if AllChem.MMFFHasAllMoleculeParams(molecule):
        converged = AllChem.MMFFOptimizeMolecule(molecule, maxIters=300) == 0
        method += ' + MMFF94'
    elif AllChem.UFFHasAllMoleculeParams(molecule):
        converged = AllChem.UFFOptimizeMolecule(molecule, maxIters=300) == 0
        method += ' + UFF'
    Chem.Kekulize(molecule, clearAromaticFlags=True)
    conf = molecule.GetConformer()
    atoms = []
    for atom in molecule.GetAtoms():
        p = conf.GetAtomPosition(atom.GetIdx())
        entry = dict(el=atom.GetSymbol(), x=p.x, y=p.y, z=p.z)
        for field, value in (('charge', atom.GetFormalCharge()), ('isotope', atom.GetIsotope()), ('radical', atom.GetNumRadicalElectrons())):
            if value:
                entry[field] = value
        atoms.append(entry)
    bonds = [dict(a=b.GetBeginAtomIdx(), b=b.GetEndAtomIdx(), order=round(b.GetBondTypeAsDouble()), **({'kind':'dative'} if b.GetBondType() == Chem.BondType.DATIVE else {})) for b in molecule.GetBonds()]
    result = dict(name=name, atoms=atoms, bonds=bonds, smiles=Chem.MolToSmiles(Chem.RemoveHs(molecule)), embedding=method)
    note = f'3D conformer generated locally with {method}.'
    if not converged:
        note += ' Relaxation reached its iteration limit.'
    return result, note
