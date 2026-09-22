"""Official FAIR-Chem 2.22.0 local-checkpoint loading; no implicit downloads."""
def create(path, config, structure):
    from fairchem.core import FAIRChemCalculator
    from fairchem.core.units.mlip_unit import load_predict_unit, InferenceSettings
    # Batch keeps unmerged MOLE; disable compile to avoid cold-start compiler/toolchain requirements.
    settings=InferenceSettings(compile=False,merge_mole=False)
    predictor=load_predict_unit(str(path),inference_settings=settings,device=config['device'],seed=config['seed'])
    return FAIRChemCalculator(predictor,task_name='omol',seed=config['seed'])
