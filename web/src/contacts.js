import {vdWR} from './chemistry.js';

// Geometry-only suggestions: explicit H bonds, halogen bonds and short vdW
// contacts. These do not assign interaction energies or electronic structure.
export function detectContacts({atoms,bonds}) {
  const neighbors=atoms.map(()=>new Set()),contacts=[],cells=new Map(),width=4.2;
  for(const {a,b} of bonds){neighbors[a].add(b);neighbors[b].add(a);}
  const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);
  const acceptor=i=>['N','O','S','F'].includes(atoms[i].el) &&
    !(atoms[i].el==='N' && (atoms[i].charge>0 || neighbors[i].size>=4));
  const directed=(tip,other)=>{
    const atom=atoms[tip],adj=[...neighbors[tip]];
    const hydrogen=atom.el==='H',halogen=['Cl','Br','I'].includes(atom.el);
    if(!hydrogen&&!halogen)return null;
    if(adj.length!==1||!acceptor(other))return false;
    const donor=atoms[adj[0]],target=atoms[other];
    if(hydrogen&&!['N','O','S'].includes(donor.el))return false;
    const u=[donor.x-atom.x,donor.y-atom.y,donor.z-atom.z];
    const v=[target.x-atom.x,target.y-atom.y,target.z-atom.z];
    const cosine=u.reduce((s,x,k)=>s+x*v[k],0)/(Math.hypot(...u)*Math.hypot(...v));
    return cosine <= (hydrogen?-.5:-Math.sqrt(3)/2) &&
      (!hydrogen || (distance(atom,target)<=2.7 && distance(donor,target)<=3.6))
      ? (hydrogen?'hydrogen':'halogen') : false;
  };
  atoms.forEach((atom,i)=>{
    const cell=[atom.x,atom.y,atom.z].map(x=>Math.floor(x/width));
    // Exclude bonded, 1–3 and 1–4 neighbors, including existing annotations.
    const excluded=new Set([i]);let frontier=[i];
    for(let depth=0;depth<3;depth++){
      const next=[];
      for(const k of frontier)for(const j of neighbors[k])if(!excluded.has(j)){excluded.add(j);next.push(j);}
      frontier=next;
    }
    for(let x=-1;x<=1;x++)for(let y=-1;y<=1;y++)for(let z=-1;z<=1;z++){
      for(const j of cells.get([cell[0]+x,cell[1]+y,cell[2]+z].join(','))||[]){
        if(excluded.has(j))continue;
        const other=atoms[j],r1=vdWR[atom.el],r2=vdWR[other.el];
        if(atom.structureIndex!==other.structureIndex)continue; // Comparison overlays are independent structures.
        if(!r1||!r2)continue; // Do not invent radii for unsupported elements.
        const d=distance(atom,other),sum=r1+r2;
        if(d<.55*sum||d>sum)continue;
        const a=directed(i,j),b=directed(j,i);
        const kind=a||b||(a===null&&b===null&&d<=.95*sum?'close':null);
        if(kind)contacts.push({a:j,b:i,kind,distance:d});
      }
    }
    const key=cell.join(',');if(!cells.has(key))cells.set(key,[]);cells.get(key).push(i);
  });
  return contacts;
}
