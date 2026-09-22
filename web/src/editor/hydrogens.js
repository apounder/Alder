import { Vector3 } from 'three';
import { maxValence, idealLength } from '../chemistry.js';
import { point } from './placement.js';

export function removeAtoms(model, ids) {
  const removed=new Set(ids), map=new Map();
  model.atoms=model.atoms.filter((a,i)=>{if(removed.has(i))return false;map.set(i,map.size);return true;});
  model.bonds=model.bonds.filter(b=>map.has(b.a)&&map.has(b.b)).map(b=>({...b,a:map.get(b.a),b:map.get(b.b)}));
  return map;
}
function hydrogenDirections(model,i,others,count) {
  const a=model.atoms[i],p=point(a),axes=others.map(j=>point(model.atoms[j]).sub(p).normalize());
  const orders=model.bonds.filter(b=>b.a===i||b.b===i).map(b=>b.order);
  const linear=orders.includes(3)||orders.filter(o=>o===2).length===2;
  const planar=orders.some(o=>o>1);
  if(!axes.length) {
    if(a.el==='O') {const half=104.5*Math.PI/360;return [new Vector3(Math.cos(half),Math.sin(half),0),new Vector3(Math.cos(half),-Math.sin(half),0)];}
    return [[1,1,1],[1,-1,-1],[-1,1,-1],[-1,-1,1]].map(v=>new Vector3(...v).normalize());
  }
  if(axes.length===1) {
    const axis=axes[0],u=new Vector3(Math.abs(axis.y)<0.9?0:1,Math.abs(axis.y)<0.9?1:0,0).cross(axis).normalize(),v=axis.clone().cross(u);
    const cos=linear ? -1 : planar ? -.5 : a.el==='O' ? Math.cos(104.5*Math.PI/180) : -1/3;
    return Array.from({length:count},(_,k)=>{
      const angle=planar ? k*Math.PI : k*2*Math.PI/3;
      return axis.clone().multiplyScalar(cos).addScaledVector(u,Math.sqrt(1-cos*cos)*Math.cos(angle)).addScaledVector(v,Math.sqrt(1-cos*cos)*Math.sin(angle)).normalize();
    });
  }
  const bisector=axes.reduce((v,d)=>v.sub(d),new Vector3()).normalize();
  if(bisector.lengthSq()<1e-8)bisector.set(0,0,1);
  if(count===1)return [bisector];
  let normal=axes[0].clone().cross(axes[1]).normalize();
  if(normal.lengthSq()<1e-8)normal=new Vector3(1,0,0).cross(bisector).normalize();
  return [1,-1].map(sign=>bisector.clone().multiplyScalar(1/Math.sqrt(3)).addScaledVector(normal,sign*Math.sqrt(2/3)).normalize());
}

// Neutral main-group valences only. Charged atoms and metals need explicit editing.
// Existing atoms retain order; only surplus terminal H atoms are removed.
export function adjustHydrogens(model, selection=[], centers=null, {add=true}={}) {
  const allowed=centers===null ? null : new Set(centers);
  const neighbors=model.atoms.map(()=>[]);
  model.bonds.forEach(b=>{neighbors[b.a].push([b.b,b.order]);neighbors[b.b].push([b.a,b.order]);});
  const remove=[],changed=new Set();
  model.atoms.forEach((a,i)=>{
    if(allowed&&!allowed.has(i))return;
    if(a.el==='H'||a.charge||a.radical||!maxValence[a.el])return;
    const hs=neighbors[i].filter(([j,o])=>model.atoms[j].el==='H'&&neighbors[j].length===1&&o===1);
    const occupied=neighbors[i].filter(([j])=>!hs.some(([h])=>j===h)).reduce((sum,[,o])=>sum+(o===4?1.5:o),0);
    const needed=Math.max(0,Math.floor(maxValence[a.el]-occupied));
    if(hs.length>needed||(add&&hs.length<needed))changed.add(i);
    remove.push(...hs.slice(needed).map(([j])=>j));
  });
  const map=removeAtoms(model,remove);
  selection=selection.filter(i=>map.has(i)).map(i=>map.get(i));
  const changedCenters=[...changed].map(i=>map.get(i));
  for(const i of changedCenters) {
    const a=model.atoms[i],ns=model.bonds.filter(b=>b.a===i||b.b===i).map(b=>[b.a===i?b.b:b.a,b.order]);
    const hs=ns.filter(([j,o])=>model.atoms[j].el==='H'&&o===1&&model.bonds.filter(b=>b.a===j||b.b===j).length===1).map(([j])=>j);
    const others=ns.filter(([j])=>!hs.includes(j));
    const needed=Math.max(0,Math.floor(maxValence[a.el]-others.reduce((s,[,o])=>s+(o===4?1.5:o),0)));
    const dirs=hydrogenDirections(model,i,others.map(([j])=>j),needed);
    for(let k=0;k<needed;k++) {
      const p=point(a).addScaledVector(dirs[k%dirs.length],idealLength(a.el,'H'));
      if(k<hs.length)Object.assign(model.atoms[hs[k]],{x:p.x,y:p.y,z:p.z});
      else {const b=model.atoms.length;model.atoms.push({el:'H',x:p.x,y:p.y,z:p.z});model.bonds.push({a:i,b,order:1});}
    }
  }
  return selection;
}
