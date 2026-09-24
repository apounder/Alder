"""Bounded calculation pages for the existing result, comparison and export views."""
import numpy as np
from ase.units import Hartree
from .data import Calculation
from .paths import ReactionPath


def calculation_page(store,ident,start=0,limit=200,indices=None):
    job=store.job(ident);data=job['input'];s=data['structure']
    frames=store.frames(ident,start,limit) if indices is None else [(i,store.get_frame(ident,i)) for i in indices[:1000]]
    if not frames:raise ValueError('This job has no saved frames yet.')
    numbers=[i for i,_ in frames];lookup={i:j for j,i in enumerate(numbers)}
    rows=[r for _,r in frames]
    calculation=Calculation(f'{s.get("name","Molecule")} · {data["kind"]} · {ident[:8]}',np.array(s['numbers']),
        np.array([r['positions'] for r in rows]),np.array([r['energy']/Hartree for r in rows]),
        metadata=dict(package='Alder MLIP',energy_label='MLIP potential energy',trajectory=True,
            mlip_job=ident,mlip_frames=numbers,mlip_input=s,mlip_rows=rows,periodic=False,max_forces=[r['max_force'] for r in rows]),
        summary={'State':job['status'],'Job':data['kind'],'Checkpoint':data['model'].get('checkpoint','Local'),
                 'Charge / multiplicity':f'{s["charge"]} / {s["multiplicity"]}',
                 'Saved frames':f'{numbers[0]+1}–{numbers[-1]+1} of {store.count(ident)}'},
        warnings=['This is a bounded page of saved simulation frames. All full forces, velocities, masses, and provenance remain in the job database.'] if store.count(ident)>len(rows) else [])
    calculation.convergence={j:[('Maximum projected force / eV Å⁻¹',r['projected_max_force'],data['settings']['fmax'])] for j,r in enumerate(rows) if data['kind'] not in ('md','sp','freq')}
    freq=store.artifact(ident,'frequencies')
    workflow=store.artifact(ident,'workflow')
    if freq is None and workflow:
        freq=store.artifact(workflow['child'],'frequencies')
        calculation.metadata['frequency_job']=workflow['child']
    if freq:
        calculation.frequencies=np.array(freq['frequencies']);calculation.ir_intensities=np.full(len(freq['frequencies']),np.nan);calculation.raman_activities=np.full(len(freq['frequencies']),np.nan);calculation.displacements=np.array(freq['modes']);calculation.vibration_coords=np.array(freq['positions'])
        calculation.warnings.append('Constrained tangent-space frequencies; not a full free-molecule analysis.' if freq['partial'] else 'Mass-weighted molecular frequencies with translations/rotations projected out; IR/Raman intensities are unavailable.')
    points=[];labels=[];kind=None
    scan=store.artifact(ident,'scan')
    if scan:
        kind='Scan';labels=[d['kind'].title()+'('+','.join(str(i+1) for i in d['atoms'])+') / '+('Å' if d['kind']=='bond' else '°') for d in scan['axes']]
        points=[(p['targets'],p['energy'],p['frame']) for p in scan['points']]
    irc=store.artifact(ident,'irc')
    if irc:
        kind='IRC';labels=['Reaction coordinate / √amu Å'];points=sorted(([p['coordinate']],p['energy'],p['frame']) for b in irc['branches'] for p in b['points'])
    neb=store.artifact(ident,'neb')
    if neb:
        kind='NEB';labels=['Band coordinate / Å'];points=[([p['coordinate']],p['energy'],p['frame']) for p in neb['history'][-1]['images']]
    if points:
        calculation.reaction_path=ReactionPath(kind,labels,np.array([p[0] for p in points]),
            np.array([p[1]/Hartree if p[1] is not None else np.nan for p in points]),np.array([lookup.get(p[2],-1) for p in points]))
    return calculation
