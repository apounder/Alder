"""Maintained AIMNetCentral 0.2.0 interface, including checkpoint-owned corrections."""
def create(path, config, structure):
    import torch
    # Official eager execution avoids an implicit C++ compiler dependency in neighbor kernels.
    torch.compiler.set_stance("force_eager")
    from aimnet.calculators import AIMNet2Calculator, AIMNet2ASE
    if config['precision']!='float32': raise ValueError('AIMNetCentral currently uses float32 input/model tensors.')
    core=AIMNet2Calculator(str(path),device=config['device'],compile_model=False)
    if structure['multiplicity']!=1 and not core.is_nse:
        raise ValueError('This local AIMNet checkpoint is not an NSE spin-conditioned model.')
    return AIMNet2ASE(core,charge=structure['charge'],mult=structure['multiplicity'])
