import { Matrix4, Quaternion, Vector3 } from 'three';
import { idealLength, validateModel, vdWR } from '../chemistry.js';
import { point, neighbors } from './placement.js';
import { adjustHydrogens, removeAtoms } from './hydrogens.js';

function frame(x, y) {
  x=x.clone().normalize();
  if(x.lengthSq()<1e-8)x.set(1,0,0);
  y=y.clone().addScaledVector(x,-y.dot(x));
  if(y.lengthSq()<1e-8)y=new Vector3(Math.abs(x.y)<.9?0:1,Math.abs(x.y)<.9?1:0,0).addScaledVector(x,-(Math.abs(x.y)<.9?x.y:x.x));
  y.normalize();
  return new Matrix4().makeBasis(x,y,new Vector3().crossVectors(x,y));
}
const sum = vectors => vectors.reduce((a,b)=>a.add(b),new Vector3());
const bondOrder = (model,a,b) => model.bonds.find(bond=>(bond.a===a&&bond.b===b)||(bond.a===b&&bond.b===a))?.order || 1;

// Pure planning: preview and commit use exactly the same assembly, with no mutation
// until the complete candidate has valid coordinates and connectivity.
export function planFragment(model, fragment, {root=0,anchor=null,mode='replace',position=null,hydrogens=true}={}) {
  fragment=fragment.model || fragment;
  if(!fragment.atoms[root]||fragment.atoms[root].el==='H')throw Error('Choose a heavy atom as the fragment joining atom.');
  if(anchor!==null&&!model.atoms[anchor])throw Error('Select an atom to place this fragment.');
  if(!['replace','attach'].includes(mode))throw Error('Choose Replace atom or Attach by bond.');
  const source=point(fragment.atoms[root]);
  const inside=neighbors(fragment,root).filter(i=>fragment.atoms[i].el!=='H').map(i=>point(fragment.atoms[i]).sub(source).normalize());
  const sourceFrame=frame(sum(inside),inside.length>1?inside[0].clone().sub(inside[1]):new Vector3(0,0,1));
  const candidate=structuredClone(model),retained=new Set(candidate.atoms);
  let parent=null,removeH=null,origin,axis=new Vector3(1,0,0),orientation=new Quaternion(),spiro=false;
  const oldHydrogens=anchor!==null&&mode==='replace'&&hydrogens?neighbors(model,anchor).filter(i=>model.atoms[i].el==='H'&&neighbors(model,i).length===1):[];
  if(anchor===null) {
    origin=position?.clone() || new Vector3(model.atoms.length?Math.max(...model.atoms.map(a=>a.x))+4:0,0,0);
  } else {
    const old=model.atoms[anchor],ns=neighbors(model,anchor);
    const heavy=ns.filter(i=>model.atoms[i].el!=='H');
    if(mode==='attach') {
      parent=anchor;
      if(old.el==='H'&&ns.length===1){removeH=anchor;parent=ns[0];}
      else removeH=ns.find(i=>model.atoms[i].el==='H'&&neighbors(model,i).length===1&&bondOrder(model,anchor,i)===1)??null;
      const p=point(model.atoms[parent]);
      axis=removeH!==null?point(model.atoms[removeH]).sub(p):sum(neighbors(model,parent).map(i=>point(model.atoms[i]).sub(p).normalize())).negate();
      if(axis.lengthSq()<1e-8)axis.set(1,0,0);
      axis.normalize();origin=p.addScaledVector(axis,idealLength(model.atoms[parent].el,fragment.atoms[root].el));
    } else {
      origin=point(old);
      const outside=heavy.map(i=>point(model.atoms[i]).sub(origin).normalize());
      axis=sum(outside).negate();
      if(axis.lengthSq()<1e-8)axis=outside.length?new Vector3().crossVectors(outside[0],new Vector3(0,0,1)):new Vector3(1,0,0);
      if(axis.lengthSq()<1e-8)axis.set(1,0,0);
      axis.normalize();
      if(old.el==='H'&&ns.length===1)origin=point(model.atoms[ns[0]]).addScaledVector(axis,idealLength(model.atoms[ns[0]].el,fragment.atoms[root].el,bondOrder(model,anchor,ns[0])));
      spiro=outside.length===2&&inside.length===2;
    }
    // Two retained bonds and two ring bonds occupy perpendicular local planes.
    const outside=heavy.map(i=>point(model.atoms[i]).sub(point(old)).normalize());
    const across=spiro?new Vector3().crossVectors(outside[0],outside[1]):new Vector3(0,0,1);
    orientation.setFromRotationMatrix(frame(axis,across).multiply(sourceFrame.clone().transpose()));
  }
  const local=model.atoms.map((a,i)=>({a,i,p:point(a)})).filter(({a,i,p})=>a.el!=='H'&&!(mode==='replace'&&i===anchor)&&p.distanceTo(origin)<10);
  let best=null,bestScore=Infinity;
  // Only the new group moves. A short torsion search avoids clashes without
  // distorting an imported structure or flattening a saturated ring.
  for(let step=0;step<(anchor===null?1:spiro?2:12);step++) {
    const twist=new Quaternion().setFromAxisAngle(axis,step*(spiro?Math.PI:Math.PI/6)).multiply(orientation);
    const atoms=fragment.atoms.map(a=>{const p=point(a).sub(source).applyQuaternion(twist).add(origin);return {...a,x:p.x,y:p.y,z:p.z};});
    let score=step*1e-7;
    for(let i=0;i<atoms.length;i++) {
      if(i===root||atoms[i].el==='H')continue;
      for(const {a,p} of local)score+=Math.max(0,.7*((vdWR[a.el]||1.6)+(vdWR[atoms[i].el]||1.6))-p.distanceTo(point(atoms[i])))**2;
    }
    if(score<bestScore){bestScore=score;best=atoms;}
  }
  const rootAtom=best[root],map=new Map();
  if(anchor!==null&&rootAtom.radical) {
    const external=mode==='attach'?1:model.bonds.filter(b=>b.a===anchor||b.b===anchor).filter(b=>!oldHydrogens.includes(b.a===anchor?b.b:b.a)).reduce((n,b)=>n+b.order,0);
    rootAtom.radical=Math.max(0,rootAtom.radical-external);if(!rootAtom.radical)delete rootAtom.radical;
  }
  if(anchor!==null&&mode==='replace'){candidate.atoms[anchor]=rootAtom;map.set(root,anchor);}
  for(let i=0;i<best.length;i++)if(!map.has(i)){map.set(i,candidate.atoms.length);candidate.atoms.push(best[i]);}
  for(const b of fragment.bonds)candidate.bonds.push({...b,a:map.get(b.a),b:map.get(b.b)});
  if(parent!==null)candidate.bonds.push({a:parent,b:map.get(root),order:1});
  const parentAtom=parent===null?null:candidate.atoms[parent];
  removeAtoms(candidate,[...oldHydrogens,...(removeH===null?[]:[removeH])]);
  // Joining caps must leave on both sides of the bond, even when automatic
  // hydrogen filling is off. In that mode only trim the junctions, never fill
  // open valences elsewhere in the fragment or the existing structure.
  const centers=candidate.atoms.flatMap((a,i)=>(hydrogens?!retained.has(a):a===rootAtom)||a===parentAtom?[i]:[]);
  adjustHydrogens(candidate,[],centers,{add:hydrogens});
  const selected=candidate.atoms.indexOf(rootAtom);
  if(selected<0)throw Error('The fragment junction could not be retained.');
  if(!model.atoms.length)candidate.name=fragment.name;
  candidate.smiles='';
  const added=new Set(candidate.atoms.flatMap((a,i)=>!retained.has(a)?[i]:[])),previewMap=new Map(),preview={atoms:[],bonds:[]};
  for(const b of candidate.bonds)if(added.has(b.a)||added.has(b.b))for(const i of [b.a,b.b]) {
    if(!previewMap.has(i)){previewMap.set(i,preview.atoms.length);preview.atoms.push({...candidate.atoms[i],previewExisting:!added.has(i),junction:i===selected});}
  }
  for(const i of added)if(!previewMap.has(i)){previewMap.set(i,preview.atoms.length);preview.atoms.push({...candidate.atoms[i],junction:i===selected});}
  for(const b of candidate.bonds)if(added.has(b.a)||added.has(b.b))preview.bonds.push({...b,a:previewMap.get(b.a),b:previewMap.get(b.b)});
  return {model:validateModel(candidate),selection:[selected],preview};
}
