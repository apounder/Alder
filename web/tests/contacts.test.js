import test from 'node:test';
import assert from 'node:assert/strict';
import {detectContacts} from '../src/contacts.js';
import '../../src/alder/assets/appearance.js';

test('geometry contacts respect donor angles, exclusions, motion and do not mutate bonds',()=>{
  const model={atoms:[{el:'O',x:0,y:0,z:0},{el:'H',x:1,y:0,z:0},{el:'O',x:2.8,y:0,z:0}],bonds:[{a:0,b:1,order:1}]};
  const before=JSON.stringify(model);
  assert.ok(detectContacts(model).some(c=>c.a===1&&c.b===2&&c.kind==='hydrogen'));
  assert.equal(JSON.stringify(model),before);
  model.atoms[2]={el:'O',x:1,y:1.8,z:0};
  assert.ok(!detectContacts(model).some(c=>c.kind==='hydrogen'),'reject bent donor geometry');
  model.atoms[2].x=20;assert.deepEqual(detectContacts(model),[]);
  model.atoms[2]={el:'O',x:2.8,y:0,z:0};model.bonds.push({a:0,b:2,order:1});
  assert.deepEqual(detectContacts(model),[],'exclude 1–3 pairs');
  const halogen={atoms:[{el:'C',x:0,y:0,z:0},{el:'Cl',x:1.7,y:0,z:0},{el:'O',x:4.7,y:0,z:0}],bonds:[{a:0,b:1,order:1}]};
  assert.equal(detectContacts(halogen)[0].kind,'halogen');
  halogen.atoms[2]={el:'O',x:1.7,y:3,z:0};assert.deepEqual(detectContacts(halogen),[]);
  const pair={atoms:[{el:'C',x:-.1,y:0,z:0},{el:'C',x:3,y:0,z:0}],bonds:[]};
  assert.equal(detectContacts(pair)[0].kind,'close','spatial bins work across zero');
  pair.atoms[1].x=.1;assert.deepEqual(detectContacts(pair),[],'clashes are not contacts');
  pair.atoms[1].x=3;pair.bonds=[{a:0,b:1,kind:'ts'}];assert.deepEqual(detectContacts(pair),[]);
});

test('figure presets have distinct material and bond settings',()=>{
  const get=globalThis.MoleculeAppearance.settings;
  assert.equal(get('Flat').flat,true);
  assert.ok(get('Tube').elementBonds);
  assert.ok(get('Tube').bondRadius>get('Wire').bondRadius);
  assert.ok(get('Ball and tube').elementBonds);
  assert.equal(get('vdW').scale,1);
  assert.equal(get('Studio').scale,.25);
});
