"""Only imported in worker processes; calculator configuration is algorithm-independent."""
import importlib
import importlib.metadata
import platform
from ..registry import model_path, validate_model


def create(data, cache):
    import torch
    config=data['model']; validate_model(config,data['structure'],data['kind'])
    device=config['device']
    if device=='cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA is unavailable in this backend environment; select CPU explicitly.')
    torch.set_num_threads(data['settings']['threads'])
    torch.manual_seed(data['settings']['seed'])
    path,spec=model_path(config,cache)
    module=importlib.import_module('.'+config['backend'],__package__)
    calculator=module.create(path,config|{'seed':data['settings']['seed'],'head':config.get('head') or spec['head']},data['structure'])
    versions={}
    for name in ('ase','numpy','scipy','torch','fairchem-core','mace-torch','aimnet','sella','rdkit','e3nn','nvalchemi-toolkit-ops','warp-lang','jax','jaxlib','huggingface-hub'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    provenance=dict(model=spec,device=device,precision=config['precision'],task=spec['task'],head=spec['head'],
                    corrections=spec['correction'],software=versions,python=platform.python_version(),platform=platform.platform())
    if config['backend']=='mace':
        provenance['resolved_head']=calculator.head
    if config['backend']=='aimnet2':
        core=calculator.base_calc;metadata=getattr(core.model,'_metadata',{}) or {}
        provenance['resolved_corrections']={k:metadata.get(k) for k in ('needs_coulomb','needs_dispersion','d3_params')}
        provenance['resolved_corrections'].update(external_coulomb=type(core.external_coulomb).__name__ if core.external_coulomb else None,
            external_dispersion=type(core.external_dftd3).__name__ if core.external_dftd3 else None,
            additional_corrections=False)
    return calculator,provenance
