import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  parseMOL,
  parseXYZ,
  parsePDB,
  parseFile,
  formula,
  idealLength,
  validateModel,
  CPK,
  elements,
} from "../src/chemistry.js";
import {
  writeMOL,
  writeXYZ,
  writePDB,
  readHash,
  shareHash,
} from "../src/io.js";
import { measure } from "../src/measure.js";
import { relax } from "../src/editor/relax.js";
import { fallbackEmbed } from "../src/rdkit.js";
const aspirin = parseMOL(fs.readFileSync("src/fixtures/aspirin.mol", "utf8"));
test('Every element has a color in all Studio presets, with explicit overlay colors taking precedence', async()=>{
  const {StudioView}=await import('../src/studio-view.js');
  assert.equal(elements.length,118);
  assert.deepEqual(Object.keys(CPK).sort(),[...elements].sort());
  assert.equal(new Set(Object.values(CPK)).size,118);
  for(const preset of ['Studio','Paton-inspired','Soft studio']) {
    const view={preset:MoleculeAppearance.settings(preset)};
    for(const el of elements) {
      assert.match(CPK[el],/^#[0-9A-F]{6}$/);
      const color=StudioView.prototype.color.call(view,{el});
      assert.equal(color,view.preset.colors[el]||CPK[el]);
      assert.equal(StudioView.prototype.color.call(view,{el,structureColor:'#123456'}),'#123456');
    }
    const main=['H','C','N','O','F','P','S','Cl','Br','I'].map(el=>StudioView.prototype.color.call(view,{el}).toUpperCase());
    for(const el of elements.filter(el=>!['H','C','N','O','F','P','S','Cl','Br','I'].includes(el)))
      assert.ok(!main.includes(CPK[el]),`${el} duplicates a familiar main-group color`);
  }
});
test('Dative and TS annotations preserve direction, hydrogen counts, MOL/hash round trips, and undo', async()=>{
  const {StudioEditor}=await import('../src/editor/studio-editor.js');
  const {adjustHydrogens}=await import('../src/editor/hydrogens.js');
  let model={name:'contacts',atoms:[{el:'N',x:0,y:0,z:0},{el:'Zn',x:3,y:0,z:0},{el:'O',x:0,y:3,z:0}],bonds:[]};
  adjustHydrogens(model);const before=structuredClone(model);
  const canvas={addEventListener(){},style:{}};
  const view={renderer:{domElement:canvas},style:{spin:false},controls:{enabled:true},camera:{getWorldDirection:v=>v.set(0,0,1)},visible:()=>true,updateOverlays(){},showGhost(){},fit(){}};
  const editor=new StudioEditor(view,{getModel:()=>model,onChange:m=>model=m,onState(){},toast(){}});
  editor.bondKind='dative';editor.setBond(0,1);editor.bondKind='ts';editor.setBond(0,2);
  assert.deepEqual(model.atoms,before.atoms);
  adjustHydrogens(model);assert.deepEqual(model.atoms,before.atoms);
  assert.deepEqual(parseMOL(writeMOL(model)).bonds,model.bonds);
  assert.deepEqual(readHash(shareHash(model,{})).bonds,model.bonds);
  editor.bondKind='dative';editor.setBond(1,0);
  assert.equal(model.bonds.find(b=>b.kind==='dative').a,1);
  editor.undo();assert.equal(model.bonds.find(b=>b.kind==='dative').a,0);
  editor.undo();editor.undo();assert.deepEqual(model,before);
  const contact={atoms:[{el:'C',x:0,y:0,z:0},{el:'C',x:4,y:0,z:0}],bonds:[{a:0,b:1,order:1,kind:'ts'}]};
  await relax(contact);assert.equal(contact.atoms[1].x,4);
});
test("V2000 aspirin fixture: valid connectivity, explicit H, sensible lengths", () => {
  assert.equal(aspirin.atoms.length, 21);
  assert.equal(aspirin.bonds.length, 21);
  assert.equal(formula(aspirin), "C₉H₈O₄");
  for (const b of aspirin.bonds) {
    const a = aspirin.atoms[b.a],
      c = aspirin.atoms[b.b],
      d = Math.hypot(a.x - c.x, a.y - c.y, a.z - c.z);
    assert.ok(d > 0.85 && d < 1.65, `${b.a}-${b.b}: ${d}`);
  }
});
test("MOL exact order/bond/charge round trip; XYZ 4-decimal round trip", () => {
  aspirin.atoms[0].charge = 1;
  const mol = parseMOL(writeMOL(aspirin));
  assert.deepEqual(mol.atoms, aspirin.atoms);
  assert.deepEqual(mol.bonds, aspirin.bonds);
  const xyz = parseXYZ(writeXYZ(aspirin));
  assert.deepEqual(
    xyz.atoms.map(({ el, x, y, z }) => ({ el, x, y, z })),
    aspirin.atoms.map(({ el, x, y, z }) => ({ el, x, y, z })),
  );
  assert.equal(writeXYZ(aspirin).trim().split("\n").length, 23);
  assert.match(writeXYZ(aspirin), /\d\.\d{4}/);
});
test("PDB geometry, atom symbols, and explicit bond orders round trip", () => {
  const pdb = parsePDB(writePDB(aspirin));
  assert.equal(pdb.atoms.length, 21);
  assert.deepEqual(
    pdb.atoms.map((a) => a.el),
    aspirin.atoms.map((a) => a.el),
  );
  assert.deepEqual(
    pdb.bonds,
    aspirin.bonds
      .map((b) => ({ ...b, a: Math.min(b.a, b.b), b: Math.max(b.a, b.b) }))
      .sort((a, b) => a.a - b.a || a.b - b.b),
  );
  for (let i = 0; i < 21; i++)
    for (const k of ["x", "y", "z"])
      assert.ok(Math.abs(pdb.atoms[i][k] - aspirin.atoms[i][k]) <= 0.0005);
});
test("SDF first record and malformed inputs reject without guessing", () => {
  let note = "";
  assert.equal(
    parseFile(
      writeMOL(aspirin) + "$$$$\n" + writeMOL(aspirin),
      "multi.sdf",
      (s) => (note = s),
    ).atoms.length,
    21,
  );
  assert.match(note, /2 records/);
  assert.throws(() => parseXYZ("2\nmissing\nC 0 0 0"));
  assert.throws(() => parseMOL("bad"));
  assert.throws(() =>
    validateModel({ atoms: [{ el: "Xx", x: 0, y: 0, z: 0 }], bonds: [] }),
  );
  assert.throws(() =>
    validateModel({
      atoms: [{ el: "C", x: 0, y: 0, z: 0 }],
      bonds: [{ a: 0, b: 2, order: 1 }],
    }),
  );
});
test("Compressed share preserves atom order, bonds and style, never history", () => {
  const style = {
    representation: "space",
    size: 1.2,
    hydrogens: false,
    background: "transparent",
  };
  const data = readHash(
    shareHash({ ...aspirin, undoStack: ["SECRET"] }, style),
  );
  assert.deepEqual(data.atoms, aspirin.atoms);
  assert.deepEqual(data.bonds, aspirin.bonds);
  assert.equal(data.style.background, "transparent");
  assert.equal(data.undoStack, undefined);
  assert.throws(() => readHash("#m=broken"));
});
test("Measurement formulas and degenerate geometry", () => {
  const a = [
    { x: 1, y: 0, z: 0 },
    { x: 0, y: 0, z: 0 },
    { x: 0, y: 1, z: 0 },
    { x: 0, y: 1, z: 1 },
  ];
  assert.equal(measure(a, [0, 1]).value, 1);
  assert.equal(measure(a, [0, 1, 2]).value, 90);
  assert.equal(Math.abs(measure(a, [0, 1, 2, 3]).value), 90);
  assert.ok(Number.isNaN(measure(a, [0, 0, 1]).value));
});
test("Tidy reduces stretched bond, resolves coincident atoms, leaves finite geometry", async () => {
  const m = {
    atoms: [
      { el: "C", x: 0, y: 0, z: 0 },
      { el: "C", x: 5, y: 0, z: 0 },
      { el: "O", x: 0, y: 0.1, z: 0 },
    ],
    bonds: [{ a: 0, b: 1, order: 1 }],
  };
  await relax(m);
  assert.ok(measure(m.atoms, [0, 1]).value < 2);
  assert.ok(measure(m.atoms, [0, 2]).value > 1);
  assert.ok(m.atoms.every((a) => [a.x, a.y, a.z].every(Number.isFinite)));
  assert.equal(idealLength("O", "H"), 0.97);
});
test("Fallback water and ethane geometry", async () => {
  const water = {
    atoms: ["O", "H", "H"].map((el) => ({ el, x: 0, y: 0, z: 0 })),
    bonds: [
      { a: 0, b: 1, order: 1 },
      { a: 0, b: 2, order: 1 },
    ],
  };
  await fallbackEmbed(water);
  assert.ok(Math.abs(measure(water.atoms, [1, 0, 2]).value - 104.5) < 0.01);
  assert.ok(Math.abs(measure(water.atoms, [0, 1]).value - 0.97) < 0.001);
  const ethane = {
    atoms: ["C", "C", "H", "H", "H", "H", "H", "H"].map((el) => ({
      el,
      x: 0,
      y: 0,
      z: 0,
    })),
    bonds: [
      { a: 0, b: 1, order: 1 },
      ...[2, 3, 4].map((b) => ({ a: 0, b, order: 1 })),
      ...[5, 6, 7].map((b) => ({ a: 1, b, order: 1 })),
    ],
  };
  await fallbackEmbed(ethane);
  const d = measure(ethane.atoms, [2, 0, 1, 5]).value;
  assert.ok(Math.abs(Math.abs(d) - 60) < 0.01, `dihedral ${d}`);
});

test("PDB CONECT bond orders survive split records", () => {
  const m = {
    name: "split connectivity",
    atoms: ["C", "N", "N", "O"].map((el, i) => ({ el, x: i, y: 0, z: 0 })),
    bonds: [
      { a: 0, b: 1, order: 3 },
      { a: 0, b: 2, order: 3 },
      { a: 0, b: 3, order: 2 },
    ],
  };
  assert.deepEqual(parsePDB(writePDB(m)).bonds, m.bonds);
});

test("Large-model relaxer yields inside pair scans and reports progress", async () => {
  const originalRAF = globalThis.requestAnimationFrame;
  let frames = 0,
    progress = 0;
  globalThis.requestAnimationFrame = (fn) =>
    setTimeout(() => {
      frames++;
      fn(performance.now());
    }, 0);
  try {
    const model = {
      atoms: Array.from({ length: 2000 }, (_, i) => ({
        el: "C",
        x: i * 4,
        y: 0,
        z: 0,
      })),
      bonds: [],
    };
    await relax(model, 3, (p) => {
      progress = p;
    });
    assert.ok(frames > 0);
    assert.ok(progress > 0);
    assert.equal(model.atoms[1999].x, 7996);
  } finally {
    globalThis.requestAnimationFrame = originalRAF;
  }
});

test('Desktop hydrogen adjustment: methane, ethane, ethanol, bond order, and charged atoms', async () => {
  const {adjustHydrogens}=await import('../src/editor/hydrogens.js');
  const m={atoms:[{el:'C',x:0,y:0,z:0}],bonds:[]};
  adjustHydrogens(m);
  assert.equal(formula(m),'CH₄');
  assert.ok(Math.abs(measure(m.atoms,[1,0,2]).value-109.4712)<.001);
  m.atoms[1].el='C';m.atoms[1].x=1.54;m.atoms[1].y=0;m.atoms[1].z=0;
  adjustHydrogens(m);assert.equal(formula(m),'C₂H₆');
  const h=m.bonds.find(b=>b.a===1 && m.atoms[b.b].el==='H').b;
  m.atoms[h].el='O';adjustHydrogens(m);assert.equal(formula(m),'C₂H₆O');
  for(let i=0;i<m.atoms.length;i++) {
    const val=m.bonds.filter(b=>b.a===i||b.b===i).reduce((s,b)=>s+b.order,0);
    assert.equal(val,{C:4,O:2,H:1}[m.atoms[i].el]);
  }
  const before=structuredClone(m);adjustHydrogens(m);assert.deepEqual(m,before);
  m.bonds.find(b=>b.a===0&&b.b===1).order=2;adjustHydrogens(m);assert.equal(formula(m),'C₂H₄O');
  const ion={atoms:[{el:'N',charge:1,x:0,y:0,z:0}],bonds:[]};
  adjustHydrogens(ion);assert.equal(ion.atoms.length,1);
});

test('Desktop edit preserves unrelated open valences and restores exact snapshots', async () => {
  const {StudioEditor}=await import('../src/editor/studio-editor.js');
  let model={name:'draft',atoms:[{el:'C',x:0,y:0,z:0},{el:'C',x:8,y:0,z:0}],bonds:[]};
  const canvas={addEventListener(){},style:{}};
  const view={renderer:{domElement:canvas},style:{spin:false},controls:{enabled:true},camera:{getWorldDirection:v=>v.set(0,0,1)},
    visible:()=>true,updateOverlays(){},showGhost(){},fit(){}};
  const editor=new StudioEditor(view,{getModel:()=>model,onChange:m=>model=m,onState(){},toast(){}});
  const before=structuredClone(model);
  editor.element='O';editor.replaceAtom(0);
  assert.equal(formula(model),'CH₂O'); // the distant unsaturated C is untouched
  assert.equal(model.bonds.filter(b=>b.a===1||b.b===1).length,0);
  assert.equal(model.atoms.length,4);
  editor.undo();assert.deepEqual(model,before);
  editor.redo();assert.equal(formula(model),'CH₂O');
});

test('MOL isotope and radical annotations survive conversion exports', () => {
  const m={name:'isotope radical',atoms:[{el:'C',x:0,y:0,z:0,charge:0,isotope:13,radical:1},{el:'O',x:1.4,y:0,z:0,charge:-1}],bonds:[{a:0,b:1,order:1}]};
  assert.deepEqual(parseMOL(writeMOL(m)).atoms,m.atoms);
});

test('Click growth replaces terminal H, grows heavy centers, applies bond orders, and undoes exactly', async () => {
  const {StudioEditor}=await import('../src/editor/studio-editor.js');
  const {adjustHydrogens}=await import('../src/editor/hydrogens.js');
  let model={name:'methane',atoms:[{el:'C',x:0,y:0,z:0}],bonds:[]};adjustHydrogens(model);
  const canvas={addEventListener(){},style:{}},view={renderer:{domElement:canvas},style:{spin:false},controls:{enabled:true},camera:{getWorldDirection:v=>v.set(0,0,1)},visible:()=>true,updateOverlays(){},showGhost(){},fit(){}};
  const editor=new StudioEditor(view,{getModel:()=>model,onChange:m=>model=m,onState(){},toast(){}});
  const methane=structuredClone(model);
  editor.element='C';editor.grow(0);assert.equal(formula(model),'C₂H₆');
  let terminal=editor.selection[0];
  editor.element='O';editor.grow(terminal);assert.equal(formula(model),'C₂H₆O');
  const ethanol=structuredClone(model);editor.undo();assert.equal(formula(model),'C₂H₆');editor.redo();assert.deepEqual(model,ethanol);
  editor.undo();editor.undo();assert.deepEqual(model,methane);
  editor.element='C';editor.bondOrder=2;editor.grow(0);assert.equal(formula(model),'C₂H₄');assert.equal(model.bonds.find(b=>model.atoms[b.a].el==='C'&&model.atoms[b.b].el==='C').order,2);
  editor.undo();editor.bondOrder=3;editor.grow(0);assert.equal(formula(model),'C₂H₂');
  for(let i=0;i<model.atoms.length;i++)assert.equal(model.bonds.filter(b=>b.a===i||b.b===i).reduce((s,b)=>s+b.order,0),model.atoms[i].el==='C'?4:1);
});

test('Substitution preserves the skeleton, adjusts H in both directions, and undoes as one edit', async () => {
  const {StudioEditor}=await import('../src/editor/studio-editor.js');
  const {adjustHydrogens}=await import('../src/editor/hydrogens.js');
  let model={name:'ethane',atoms:[{el:'C',x:0,y:0,z:0},{el:'C',x:1.54,y:0,z:0}],bonds:[{a:0,b:1,order:1}]};
  adjustHydrogens(model);
  const canvas={addEventListener(){},style:{}},view={renderer:{domElement:canvas},style:{spin:false},controls:{enabled:true},visible:()=>true,updateOverlays(){},showGhost(){}};
  const editor=new StudioEditor(view,{getModel:()=>model,onChange:m=>model=m,onState(){},toast(){}});
  const ethane=structuredClone(model);
  editor.element='O';editor.replaceAtom(1);
  assert.equal(formula(model),'CH₄O');assert.deepEqual(model.atoms[1],{el:'O',x:1.54,y:0,z:0});
  assert.deepEqual(model.bonds.find(b=>b.a===0&&b.b===1),{a:0,b:1,order:1});
  const methanol=structuredClone(model);editor.undo();assert.deepEqual(model,ethane);editor.redo();assert.deepEqual(model,methanol);
  editor.element='N';editor.replaceAtom(1);assert.equal(formula(model),'CH₅N');
  editor.element='C';editor.replaceAtom(1);assert.equal(formula(model),'C₂H₆');
  const n=editor.undoStack.length;editor.replaceAtom(1);assert.equal(editor.undoStack.length,n); // same element is not another edit
  editor.element='H';editor.replaceAtom(1);assert.equal(formula(model),'CH₄');
  assert.equal(model.bonds.filter(b=>b.a===1||b.b===1).length,1);
  editor.element='Cl';editor.replaceAtom(1);assert.equal(formula(model),'CH₃Cl');
  editor.element='C';editor.selection=[1];editor.applyElement();assert.equal(formula(model),'C₂H₆');
  editor.bondOrder=2;editor.setBond(0,1);assert.equal(formula(model),'C₂H₄');
  editor.element='O';editor.replaceAtom(1);assert.equal(formula(model),'CH₂O');assert.equal(model.bonds[0].order,2);
  editor.undo();assert.equal(formula(model),'C₂H₄');
  editor.autoHydrogens=false;const count=model.atoms.length;editor.replaceAtom(1);assert.equal(model.atoms.length,count);
});

test('Prepared fragments: exact junctions, ester direction, chain extension, spiro topology, and atomic undo', async () => {
  const {planFragment}=await import('../src/editor/fragments.js');
  const {StudioEditor}=await import('../src/editor/studio-editor.js');
  const {point,neighbors}=await import('../src/editor/placement.js');
  const library=JSON.parse(fs.readFileSync(new URL('../../src/alder/assets/fragments.json',import.meta.url),'utf8'));
  const fragment=name=>library.find(f=>f.name===name),empty={name:'draft',atoms:[],bonds:[]};
  for(const f of library) {
    const p=planFragment(empty,f,{root:f.root});assert.equal(formula(p.model),formula(f.model),f.name);
    assert.equal(p.model.atoms[p.selection[0]].el,f.model.atoms[f.root].el);
  }
  const methane=fragment('Methyl').model,ethane=fragment('Ethyl').model;
  const extended=planFragment(ethane,fragment('Ethyl'),{anchor:0});assert.equal(formula(extended.model),'C₃H₈');
  const attached=planFragment(methane,fragment('Benzene'),{anchor:0,mode:'attach'});
  assert.equal(formula(attached.model),'C₇H₈');assert.deepEqual(attached.model.atoms[0],methane.atoms[0]);
  for(const [name,element] of [['Methyl ester · carbonyl side','C'],['Acetoxy ester · oxygen side','O']]) {
    const ester=planFragment(methane,fragment(name),{anchor:0,mode:'attach'});
    assert.equal(formula(ester.model),'C₃H₆O₂');
    const join=neighbors(ester.model,0).find(i=>ester.model.atoms[i].el!=='H');assert.equal(ester.model.atoms[join].el,element);
    assert.equal(ester.model.bonds.filter(b=>b.order===2).length,1);
  }
  const ring=fragment('Cyclohexane').model,spiro=planFragment(ring,fragment('Cyclopentane'),{anchor:0});
  assert.equal(formula(spiro.model),'C₁₀H₁₈');assert.equal(spiro.model.bonds.length-spiro.model.atoms.length+1,2);
  const junction=spiro.selection[0],ns=neighbors(spiro.model,junction).filter(i=>spiro.model.atoms[i].el!=='H');assert.equal(ns.length,4);
  for(let i=0;i<6;i++)assert.deepEqual(spiro.model.atoms[i],ring.atoms[i]);
  const axis=i=>point(spiro.model.atoms[i]).sub(point(spiro.model.atoms[junction])).normalize();
  assert.ok(Math.abs(axis(ns[0]).cross(axis(ns[1])).normalize().dot(axis(ns[2]).cross(axis(ns[3])).normalize()))<1e-8);
  for(const result of [extended,attached,spiro]) {
    for(let i=0;i<result.model.atoms.length;i++) {
      const atom=result.model.atoms[i],val=result.model.bonds.filter(b=>b.a===i||b.b===i).reduce((s,b)=>s+b.order,0);
      assert.equal(val,atom.el==='C'?4:1);
      for(let j=i+1;j<result.model.atoms.length;j++)assert.ok(point(atom).distanceTo(point(result.model.atoms[j]))>.35,'coincident atoms');
    }
  }
  let model=structuredClone(ring);
  const view={renderer:{domElement:{addEventListener(){},style:{}}},style:{spin:false},controls:{enabled:true},visible:()=>true,updateOverlays(){},showGhost(){},fit(){}};
  const editor=new StudioEditor(view,{getModel:()=>model,onChange:m=>model=m,onState(){},toast(){}});
  editor.insertFragment({...fragment('Cyclopentane'),mode:'replace'},{anchor:0});assert.deepEqual(model,spiro.model);
  editor.undo();assert.deepEqual(model,ring);editor.redo();assert.deepEqual(model,spiro.model);
  const before=structuredClone(model),history=editor.undoStack.length;
  assert.throws(()=>editor.insertFragment({...fragment('Ethyl'),root:999},{anchor:0}));
  assert.deepEqual(model,before);assert.equal(editor.undoStack.length,history);
});

test('Fragment substitution consumes joining hydrogens even when automatic H adjustment is off', async () => {
  const {planFragment}=await import('../src/editor/fragments.js');
  const {StudioEditor}=await import('../src/editor/studio-editor.js');
  const {neighbors}=await import('../src/editor/placement.js');
  const {maxValence}=await import('../src/chemistry.js');
  const library=JSON.parse(fs.readFileSync(new URL('../../src/alder/assets/fragments.json',import.meta.url),'utf8'));
  const methyl=library.find(f=>f.name==='Methyl'),methane=structuredClone(methyl.model),original=structuredClone(methane);
  const hydrogen=methane.atoms.findIndex(a=>a.el==='H');
  for(const f of library)for(const [root,atom] of f.model.atoms.entries()) {
    if(atom.el==='H')continue;
    const caps=neighbors(f.model,root).filter(i=>f.model.atoms[i].el==='H').length;
    if(!caps&&!atom.radical)continue; // Only joining atoms with a substitutable H or open valence.
    for(const hydrogens of [false,true])for(const [mode,anchor] of [['replace',hydrogen],['attach',hydrogen],['attach',0]]) {
      const result=planFragment(methane,f,{root,anchor,mode,hydrogens}),m=result.model;
      const context=`${f.name}, root ${root}, ${mode} at ${anchor}, auto H ${hydrogens}`;
      assert.equal(m.atoms.length,methane.atoms.length+f.model.atoms.length-(atom.radical?1:2),context);
      assert.equal(m.atoms.filter(a=>a.el!=='H').length,1+f.model.atoms.filter(a=>a.el!=='H').length,context);
      for(const [i,a] of m.atoms.entries())if(!a.charge&&!a.radical&&maxValence[a.el]) {
        const val=m.bonds.filter(b=>b.a===i||b.b===i).reduce((n,b)=>n+b.order,0);
        assert.equal(val,maxValence[a.el],context);
      }
      const junction=result.selection[0],previewRoot=result.preview.atoms.findIndex(a=>a.junction);
      assert.equal(neighbors(result.preview,previewRoot).length,neighbors(m,junction).length,context);
      assert.deepEqual(m.atoms[0],methane.atoms[0],context);
    }
  }
  assert.deepEqual(methane,original);
  // Manual hydrogen editing elsewhere remains intact; insertion and undo are atomic.
  let model={...structuredClone(methane),atoms:[...structuredClone(methane.atoms),{el:'C',x:10,y:0,z:0}]};
  const before=structuredClone(model),view={renderer:{domElement:{addEventListener(){},style:{}}},style:{spin:false},controls:{enabled:true},visible:()=>true,updateOverlays(){},showGhost(){},fit(){}};
  const editor=new StudioEditor(view,{getModel:()=>model,onChange:m=>model=m,onState(){},toast(){}});
  editor.autoHydrogens=false;
  editor.insertFragment(methyl,{anchor:hydrogen});
  assert.equal(formula(model),'C₃H₆');
  const after=structuredClone(model);assert.equal(editor.undoStack.length,1);
  editor.undo();assert.deepEqual(model,before);editor.redo();assert.deepEqual(model,after);
});


test("signed dihedrals agree with ASE and wrap at 180 degrees", () => {
  const atoms = [[-2,0,0],[0,0,0],[0,2,0],[0,2,2]].map(([x,y,z])=>({el:"C",x,y,z}));
  assert.equal(measure(atoms,[0,1,2,3]).value,90);
  atoms[3].z=-2;assert.equal(measure(atoms,[0,1,2,3]).value,-90);
  atoms[3].z=0;atoms[3].x=2;assert.equal(measure(atoms,[0,1,2,3]).value,-180);
});


test('Fragment junction geometry follows the chosen atom and rejects excess valence atomically', async () => {
  const {planFragment}=await import('../src/editor/fragments.js');
  const {point,neighbors}=await import('../src/editor/placement.js');
  const {removeAtoms}=await import('../src/editor/hydrogens.js');
  const library=JSON.parse(fs.readFileSync(new URL('../../src/alder/assets/fragments.json',import.meta.url),'utf8'));
  const fragment=name=>library.find(f=>f.name===name),methane=fragment('Methyl').model;
  for(const [name,root,expected,tolerance] of [['Vinyl',0,120,5],['Vinyl',1,120,5],['Ethyl',1,109.47,5],['Ethynyl',1,180,1],['Methoxy',0,109,10]]) {
    const f=fragment(name),inside=neighbors(f.model,root).find(i=>f.model.atoms[i].el!=='H');
    for(const autoH of [false,true])for(const mode of ['attach','replace']) {
      const anchor=mode==='attach'?0:methane.atoms.findIndex(a=>a.el==='H');
      const result=planFragment(methane,{...f,root},{anchor,mode,hydrogens:autoH}),m=result.model,j=result.selection[0];
      const next=neighbors(m,j).find(i=>i!==0&&m.atoms[i].el===f.model.atoms[inside].el);
      const center=point(m.atoms[j]),a=point(m.atoms[0]).sub(center),b=point(m.atoms[next]).sub(center);
      const angle=a.angleTo(b)*180/Math.PI;
      assert.ok(Math.abs(angle-expected)<tolerance,`${name} root ${root}: ${angle}`);
      assert.ok(Math.abs(a.length()-idealLength(m.atoms[0].el,m.atoms[j].el))<1e-8);
    }
  }
  // An implicit-H host needs the same sp2 direction as a prepared fragment.
  const vinyl=structuredClone(fragment('Vinyl').model);
  removeAtoms(vinyl,vinyl.atoms.flatMap((a,i)=>a.el==='H'?[i]:[]));
  const result=planFragment(vinyl,fragment('Methyl'),{anchor:0,mode:'attach'}),m=result.model;
  const angle=point(m.atoms[1]).sub(point(m.atoms[0])).angleTo(point(m.atoms[result.selection[0]]).sub(point(m.atoms[0])))*180/Math.PI;
  assert.ok(Math.abs(angle-120)<1e-8);
  // Every numbered atom is selectable; only chemically available sites may gain a bond.
  for(const f of library)for(let root=0;root<f.points.length;root++) {
    const atom=f.model.atoms[root],capacity=neighbors(f.model,root).filter(i=>f.model.atoms[i].el==='H').length+(atom.radical||0);
    if(capacity)assert.doesNotThrow(()=>planFragment(methane,f,{root,anchor:0,mode:'attach'}),`${f.name} ${root}`);
    else assert.throws(()=>planFragment(methane,f,{root,anchor:0,mode:'attach'}),/no room/,`${f.name} ${root}`);
  }
  const tert=fragment('tert-Butyl'),full=planFragment(methane,tert,{anchor:0,mode:'attach'});
  const before=structuredClone(full.model);
  assert.throws(()=>planFragment(full.model,fragment('Methyl'),{anchor:full.selection[0],mode:'attach'}),/no room/);
  assert.deepEqual(full.model,before);
  const ring=fragment('Cyclohexane').model;
  assert.throws(()=>planFragment(ring,fragment('Benzene'),{anchor:0,root:0}),/no room/);
});
