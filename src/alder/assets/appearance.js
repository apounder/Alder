/* Shared by the calculation viewer and the desktop builder. */
globalThis.MoleculeAppearance = {
  radii: { H:1.20, C:1.70, N:1.55, O:1.52, F:1.47, Cl:1.75, Br:1.85, I:1.98, S:1.80, P:1.80 },
  settings(preset) {
    const paton = preset === 'Paton-inspired';
    const settings = {
      bondRadius: paton ? 0.07 : 0.11,
      bondColor: paton ? '#111111' : '#424942',
      scale: paton ? 0.18 : 0.25,
      hydrogenScale: paton ? 0.13 : 0.25,
      colors: {C:paton ? '#d9d9d9' : '#969d98', H:'#fafafa',
        N:paton ? '#8080ff' : '#4265d4', O:'#e63838',
        F:'#90e050', Cl:'#1ff01f', Br:'#a62929', I:'#940094', S:'#ffff30', P:'#ff8000'}
    };
    // 3D adaptations of xyzrender's documented presets, not its SVG renderer.
    const styles = {
      'Flat': {flat:true},
      'Tube': {bondRadius:0.18, elementBonds:true},
      'Ball and tube': {bondRadius:0.14, elementBonds:true, scale:0.28, hydrogenScale:0.18},
      'Wire': {bondRadius:0.045, elementBonds:true},
      'vdW': {scale:1, hydrogenScale:1},
    };
    return Object.assign(settings, styles[preset]);
  }
};
