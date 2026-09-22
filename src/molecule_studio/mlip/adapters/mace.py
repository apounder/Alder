"""Official MACE ASE interface (mace-torch 0.3.16)."""
def create(path, config, structure):
    from mace.calculators import MACECalculator
    options=dict(model_paths=str(path),device=config['device'],default_dtype=config['precision'])
    head=config.get('head')
    if head is not None: options['head']=head
    import torch
    from unittest.mock import patch
    original = torch.jit.load
    # Legacy e3nn 0.4.4 embedded TorchScript ignores outer torch.load map_location.
    # Scope remapping to construction in this isolated, single-calculator worker.
    def load_script(*args, **kwargs):
        kwargs["map_location"] = config["device"]
        return original(*args, **kwargs)
    with patch("torch.jit.load", load_script):
        calculator = MACECalculator(**options)
    if head is not None and calculator.head != head:
        raise ValueError("Requested MACE head is absent; refusing the library’s fallback head.")
    return calculator
