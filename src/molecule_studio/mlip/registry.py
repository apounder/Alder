"""Pinned checkpoint catalogue. Technical compatibility is not chemical validation."""
import hashlib
import json
from pathlib import Path

UMA_REVISION = 'f611b917d9c68566bbbeccbb0aa0f7cad1696cb2'
OFF_REVISION = '91a78c5a9c300d1104700d9352c8bfe449227737'
CATALOGUE = {}

def add(name, backend, elements, domain, charge, spin, correction, **kw):
    CATALOGUE[name] = dict(name=name, backend=backend, elements=elements, domain=domain,
        charge=charge, spin=spin, periodic=False, properties=['energy','forces'],
        precision=['float32','float64'] if backend=='mace' else ['float32'],
        task='omol' if backend=='uma' else None, head='Default' if backend=='mace' else None, correction=correction, **kw)

add('uma-s-1p2', 'uma', list(range(1,84)),
    'OMol25 molecular task; element embeddings do not establish accuracy for every oxidation/spin state. Evaluate out-of-distribution chemistry independently.',
    'explicit', 'explicit', 'Learned OMol25 reference energy; no additional dispersion',
    repo='facebook/UMA', revision=UMA_REVISION, file='checkpoints/uma-s-1p2.pt',
    license='UMA gated model licence; obtain access at https://huggingface.co/facebook/UMA')
for size in ('small','medium','large'):
    add('MACE-OFF23-'+size, 'mace', [1,6,7,8,9,15,16,17,35,53],
        'Neutral closed-shell organic molecules and molecular condensed phases. Reactive chemistry and radicals are outside its validated training domain.',
        'neutral', 'singlet', 'Dispersion present in learned reference; no added D3',
        url=f'https://raw.githubusercontent.com/ACEsuit/mace-off/{OFF_REVISION}/mace_off23/MACE-OFF23_{size}.model',
        license='Academic Software License; noncommercial academic use: https://github.com/gabor1/ASL')

# AIMNetCentral registry version accompanying aimnet 0.2.0; explicit member 0.
AIM_ELEMENTS = [1,5,6,7,8,9,14,15,16,17,33,34,35,53]
AIM_MODELS = {}
# Populated from the official registry below; no moving aliases are used.
_DATA = Path(__file__).with_name('checkpoints.json')
if _DATA.exists():
    AIM_MODELS = json.loads(_DATA.read_text())
for name, entry in AIM_MODELS.items():
    if entry.get('backend')=='mace':
        add(name,'mace',[1,6,7,8], 'ANI-1ccx neutral closed-shell HCNO small-organic conformational domain; no general reaction-path accuracy guarantee.',
            'neutral','singlet','Learned coupled-cluster reference; no additional dispersion',**{k:v for k,v in entry.items() if k!='backend'})
    else:
        nse='nse' in name; rxn='rxn' in name
        add(name,'aimnet2',[1,6,7,8] if rxn else AIM_ELEMENTS,
            'Neutral HCNO reactive paths (wB97M).' if rxn else ('Open-shell molecular wB97M domain; not strongly multireference chemistry.' if nse else 'Isolated organic/main-group molecules and clusters; no metals or implicit solvent; closed shell.'),
            'neutral' if rxn else 'explicit','explicit' if nse else 'singlet',
            'Official checkpoint metadata controls Coulomb and D3; additional corrections disabled',
            **entry)
        CATALOGUE[name]['properties'] += ['charges'] + (['spin_charges'] if nse else [])


def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def specification(config):
    name=config.get('checkpoint')
    if config.get('local_file'):
        manifest=config.get('manifest')
        if not isinstance(manifest,dict):
            raise ValueError('Local models require a JSON capability manifest, including their SHA-256, chemical domain, elements, charge/spin policy, precision, task/head and corrections.')
        required={'name','backend','elements','domain','charge','spin','periodic','properties','precision','task','head','correction','sha256'}
        if not required<=manifest.keys() or len(manifest['sha256'])!=64:
            raise ValueError('Incomplete local-model capability manifest.')
        return manifest.copy()
    if name not in CATALOGUE:
        raise ValueError('Select a named checkpoint; changing package defaults are not accepted.')
    return CATALOGUE[name].copy()


def validate_model(config, structure, kind):
    spec=specification(config)
    if config.get('backend')!=spec['backend'] or spec['backend'] not in ('uma','mace','aimnet2'):
        raise ValueError('Checkpoint and selected calculator backend differ.')
    missing=set(structure['numbers'])-set(spec['elements'])
    if missing: raise ValueError(f'The selected checkpoint does not support atomic numbers {sorted(missing)}.')
    if config.get('device') not in ('cpu','cuda') or config.get('precision') not in spec['precision']:
        raise ValueError('This checkpoint does not support the selected device/precision setting.')
    if config.get('task',spec['task'])!=spec['task'] or (config.get('head') or spec['head'])!=spec['head']:
        raise ValueError('Task/head does not match the checkpoint capability manifest.')
    if config.get('corrections','checkpoint')!='checkpoint':
        raise ValueError('Additional corrections are disabled to prevent double counting; checkpoint corrections are recorded explicitly.')
    if spec['charge'] not in ('neutral','explicit') or spec['spin'] not in ('singlet','explicit'):
        raise ValueError('Unsupported charge/spin policy in checkpoint manifest.')
    if spec['charge']=='neutral' and structure['charge']!=0:
        raise ValueError('This model cannot represent the requested net charge.')
    if spec['spin']=='singlet' and structure['multiplicity']!=1:
        raise ValueError('This checkpoint does not condition on open-shell multiplicity; it cannot be silently ignored.')
    if spec['backend']=='mace' and (spec['charge']!='neutral' or spec['spin']!='singlet'):
        raise ValueError('This MACE adapter supports ordinary neutral/singlet MACE energy models; charge-conditioned custom architectures need their own verified interface.')
    if spec['backend']=='uma' and (spec['task']!='omol' or abs(structure['charge'])>100 or structure['multiplicity']>100):
        raise ValueError('Molecular UMA calculations require omol and the documented charge/spin ranges.')
    if spec['backend']=='uma' and len(structure['numbers'])<2:
        raise ValueError('This molecular UMA adapter requires at least two atoms. Isolated atoms need separately validated atomic-reference data, which this adapter does not load.')
    if kind in ('ts','irc','neb','scan') and not config.get('domain_ack',False):
        raise ValueError('Acknowledge the selected model’s chemical domain before a reaction-path calculation. Algorithm compatibility does not validate the chemistry.')
    if not {'energy','forces'}<=set(spec['properties']): raise ValueError('Jobs require both energy and forces.')
    return spec


def model_path(config, cache):
    spec=specification(config)
    p=Path(config['local_file']) if config.get('local_file') else Path(cache)/spec['backend']/spec['name']/('weights'+Path(spec.get('file',spec.get('url','model.pt'))).suffix)
    if not p.is_file(): raise FileNotFoundError('Weights are missing. Use Download/check model, or choose a compatible local checkpoint.')
    actual=checksum(p)
    expected=spec.get('sha256') or config.get('sha256')
    receipt=p.with_suffix(p.suffix+'.json')
    if not expected and receipt.exists(): expected=json.loads(receipt.read_text())['sha256']
    if not expected or actual!=expected: raise ValueError('Checkpoint checksum is absent or does not match. Recheck the model explicitly; execution never substitutes weights.')
    if config.get('sha256') and actual!=config['sha256']: raise ValueError('Model changed after the input snapshot was captured.')
    return p, spec|{'sha256':actual}
