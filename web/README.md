# Studio's web renderer and editors

Editable Three.js renderer, 3D builder, and Ketcher 2D adapter used by the
desktop app. The desktop's generated assets are committed in
`../src/molecule_studio/assets`, so installing or building the Windows release
does **not** require npm. See the [desktop README](../README.md) for app usage.

To change these assets, install Node.js 20.19+ or 22.12+, then run from `web`:

```sh
npm ci
npm test
npm run package:studio
npm run package:sketch
```

Commit both the changed sources and regenerated desktop assets. `src/studio.js`
is the 3D builder bridge; `src/studio-calculation.js` is the calculation view;
`src/studio-view.js` is their shared renderer; `src/sketch.js` is the 2D bridge.
The shared appearance presets live in the desktop assets directory.

`npm run dev` also starts the standalone browser editor for development.
`npm run build` produces its static site. `npm run package:portable` produces
a self-contained browser HTML in `portable/MolStudio.html`; it is separate from
the Windows desktop installer. Browser integration tests use Playwright; run
`npx playwright install chromium` and `npm run test:browser` while Vite is
running. These scripts are for developers, not desktop users.

The core tests cover parsing, editing, hydrogen substitution, fragment joining,
spirocycles, geometry, measurements, undo, export, and share-link round trips.

Third-party sources: [Three.js](https://threejs.org/) (MIT),
[RDKit](https://www.rdkit.org/) (BSD), [LZ-String](https://github.com/pieroxy/lz-string)
(MIT), and [Ketcher](https://github.com/epam/ketcher) (Apache-2.0). Build scripts
retain their notices next to the desktop assets. RDKit's vendored JS/WASM and
license are in `public/vendor/rdkit`.

`src/fixtures/aspirin.mol` is a hand-authored V2000 fixture.
`src/fixtures/1crn.pdb` is the public [RCSB PDB 1CRN](https://www.rcsb.org/structure/1CRN)
crambin structure (46 residues), downloaded from
`https://files.rcsb.org/download/1CRN.pdb` for import/performance checks.
