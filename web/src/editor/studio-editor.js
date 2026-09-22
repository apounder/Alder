import { Plane, Vector3 } from 'three';
import { Editor } from './editor.js';
import { point, placement, neighbors } from './placement.js';
import { idealLength } from '../chemistry.js';
import { adjustHydrogens, removeAtoms } from './hydrogens.js';
import {startArea, moveArea, finishArea, rotateSelection} from './area-selection.js';
import { planFragment } from './fragments.js';

export class StudioEditor extends Editor {
  constructor(view, callbacks) {
    super(view,callbacks);
    this.autoHydrogens=true;this.bondOrder=1;this.bondKind=null;this.draw=null;
    view.onFrame=()=>{if(this.drag||this.rotateDrag)this.update();};
    view.renderer.domElement.addEventListener('contextmenu',e=>e.preventDefault());
    view.renderer.domElement.addEventListener('dblclick',()=>{if(['select','rect','lasso'].includes(this.tool)){this.selection=[];this.update();}});
    view.renderer.domElement.addEventListener('lostpointercapture',()=>{if(this.draw||this.area||this.rotateDrag)this.cancel();});
    view.renderer.domElement.addEventListener('pointerleave',()=>this.clearFragmentPreview());
  }
  setTool(tool) {
    if(!this.locked && !['select','move','rotate'].includes(tool))this.view.measurementCount=0;
    super.setTool(tool);
  }
  mutate(fn, hydrogens=this.autoHydrogens) {
    super.mutate(model=>{
      // Only adjust atoms touched by this edit; preserve unrelated imported geometry.
      const ids=new Map(model.atoms.map((a,i)=>[a,i]));
      const signatures=()=>{
        const ns=model.atoms.map(()=>[]);
        model.bonds.forEach(b=>{ns[b.a].push([b.b,b.order]);ns[b.b].push([b.a,b.order]);});
        return new Map(model.atoms.map((a,i)=>[a,`${a.el}:${a.charge||0}|`+ns[i].map(([j,o])=>`${ids.get(model.atoms[j])??'new'+j}:${model.atoms[j].el}:${o}`).sort().join(',')]));
      };
      const before=hydrogens?signatures():null;
      fn(model);
      if(hydrogens) {
        const after=signatures(),changed=model.atoms.map((a,i)=>before.get(a)!==after.get(a)?i:null).filter(i=>i!==null);
        this.selection=adjustHydrogens(model,this.selection,changed);
      }
    });
  }
  delete(ids) {
    if(!ids.length)return;
    // Explicit deletion must not immediately regenerate the deleted hydrogen.
    this.mutate(m=>{removeAtoms(m,ids);this.selection=[];},false);
  }
  select(i, additive=false) {
    if(additive && !this.view.measurementCount) {
      const k=this.selection.indexOf(i);if(k<0)this.selection.push(i);else this.selection.splice(k,1);
      this.update();
    } else {
      if(this.selection.length>4)this.selection=[];
      super.select(i);
    }
  }
  setBond(a,b,order=this.bondOrder) {
    const found=this.getModel().bonds.find(bond=>(bond.a===a&&bond.b===b)||(bond.a===b&&bond.b===a));
    const kind=this.bondKind;
    if(found?.order===order&&(found.kind||null)===kind&&(kind!=='dative'||found.a===a))return;
    this.mutate(m=>{
      const bond={a,b,order:kind?1:order,...(kind?{kind}:{})};
      if(found)m.bonds.splice(m.bonds.indexOf(found),1,bond);else m.bonds.push(bond);
      this.selection=[a,b];
    },kind||found?.kind?false:this.autoHydrogens);
  }
  bond(i) {
    if(this.armed===null){this.armed=i;this.update();return;}
    const a=this.armed;this.armed=null;if(a!==i)this.setBond(a,i);this.update();
  }
  replaceAtom(index) {
    this.replaceAtoms([index]);
  }
  applyElement() {
    this.replaceAtoms(this.selection);
  }
  replaceAtoms(indices) {
    const targets=indices.filter(i=>this.getModel().atoms[i]?.el!==this.element);
    if(!targets.length){this.selection=[...indices];this.update();return;}
    this.mutate(m=>{
      const remove=[];
      for(const index of targets) {
        const a=m.atoms[index],ns=neighbors(m,index);
        if(a.el==='H'&&this.element!=='H'&&ns.length===1) {
          const parent=m.atoms[ns[0]],dir=point(a).sub(point(parent)).normalize();
          Object.assign(a,point(parent).addScaledVector(dir,idealLength(parent.el,this.element)));
        }
        // A replacement H must not retain the old atom's attached hydrogens.
        if(this.autoHydrogens&&this.element==='H')remove.push(...ns.filter(i=>m.atoms[i].el==='H'&&neighbors(m,i).length===1&&!indices.includes(i)));
        a.el=this.element;delete a.charge;delete a.isotope;delete a.radical;
      }
      const map=removeAtoms(m,remove);this.selection=indices.filter(i=>map.has(i)).map(i=>map.get(i));
    });
  }
  growthTarget(index) {
    const m=this.getModel(),atom=m.atoms[index];
    let replace=null,parent=index;
    if(atom.el==='H'&&this.element!=='H'&&neighbors(m,index).length===1) {
      replace=index;parent=neighbors(m,index)[0];
    } else if(this.autoHydrogens&&!atom.charge&&!atom.radical) {
      replace=neighbors(m,index).find(i=>m.atoms[i].el==='H'&&neighbors(m,i).length===1&&
        m.bonds.some(b=>((b.a===index&&b.b===i)||(b.b===index&&b.a===i))&&b.order===1))??null;
    }
    const origin=point(m.atoms[parent]);
    const dir=replace!==null?point(m.atoms[replace]).sub(origin):placement(m,parent,this.element,this.view.camera.getWorldDirection(new Vector3())).sub(origin);
    if(dir.lengthSq()<1e-8)dir.copy(this.view.camera.getWorldDirection(new Vector3()));
    return {replace,parent,position:origin.addScaledVector(dir.normalize(),idealLength(m.atoms[parent].el,this.element,this.bondOrder))};
  }
  grow(index) {
    const target=this.growthTarget(index);
    this.mutate(m=>{
      const a=target.parent,b=target.replace??m.atoms.length,p=target.position;
      const atom={el:this.element,x:p.x,y:p.y,z:p.z};
      if(target.replace!==null) {
        m.atoms[b]=atom;
        const bond=m.bonds.find(bond=>(bond.a===a&&bond.b===b)||(bond.b===a&&bond.a===b));
        bond.order=this.bondOrder;
      } else {m.atoms.push(atom);m.bonds.push({a,b,order:this.bondOrder});}
      this.selection=[b];
    });
  }
  drawPoint(hit) {
    const d=this.draw,m=this.getModel();
    if(hit!==null&&hit!==d.parent)return point(m.atoms[hit]);
    const p=this.view.raycaster.ray.intersectPlane(d.plane,new Vector3());
    if(!p)return null;
    if(d.parent!==null) {
      const origin=point(m.atoms[d.parent]),direction=p.clone().sub(origin);
      if(direction.lengthSq()<1e-6)return null;
      return origin.addScaledVector(direction.normalize(),idealLength(m.atoms[d.parent].el,this.element,this.bondOrder));
    }
    return p;
  }
  down(e) {
    const hit=this.view.pick(e);
    if(this.locked)return;
    if(e.button===0&&['rect','lasso'].includes(this.tool)){startArea(this,e);return;}
    if(e.button===0&&this.tool==='rotate'&&(hit!==null||this.selection.length)) {
      const snapshot=this.snapshot();
      if(hit!==null&&!this.selection.includes(hit))this.selection=[hit];
      const positions=this.selection.map(i=>[i,point(this.getModel().atoms[i])]);
      const center=positions.reduce((sum,[,p])=>sum.add(p),new Vector3()).divideScalar(positions.length);
      this.rotateDrag={snapshot,positions,center,x:e.clientX,y:e.clientY,pointerId:e.pointerId,moved:false};
      this.view.controls.enabled=false;this.view.renderer.domElement.setPointerCapture(e.pointerId);e.stopImmediatePropagation();return;
    }
    if(e.button===2) {this.rightStart={x:e.clientX,y:e.clientY,hit,bond:this.view.pickBond(e)};return;}
    if(e.button===0&&['add','fragment'].includes(this.tool)) {
      super.down(e);this.start.bond=hit===null?this.view.pickBond(e):null;return;
    }
    if(e.button===0&&this.tool==='bond') {
      if(this.bondKind){super.down(e);return;}
      const bond=hit===null?this.view.pickBond(e):null;
      const origin=hit===null?this.view.centroid():point(this.getModel().atoms[hit]);
      this.draw={parent:hit,bond,x:e.clientX,y:e.clientY,pointerId:e.pointerId,
        plane:new Plane().setFromNormalAndCoplanarPoint(this.view.camera.getWorldDirection(new Vector3()),origin)};
      this.draw.origin=this.view.raycaster.ray.intersectPlane(this.draw.plane,new Vector3());
      this.view.controls.enabled=false;this.view.renderer.domElement.setPointerCapture(e.pointerId);
      e.stopImmediatePropagation();return;
    }
    if(e.button===0&&hit===null&&this.tool==='delete') {
      const bond=this.view.pickBond(e);
      if(bond!==null){this.bondStart={bond,x:e.clientX,y:e.clientY,pointerId:e.pointerId};this.view.controls.enabled=false;e.stopImmediatePropagation();return;}
    }
    super.down(e);
  }
  move(e) {
    const hit=this.view.pick(e);
    if(this.area){moveArea(this,e);return;}
    if(this.rotateDrag){rotateSelection(this,e);return;}
    if(['add','fragment'].includes(this.tool)&&this.start&&Math.hypot(e.clientX-this.start.x,e.clientY-this.start.y)>5)this.start.moved=true;
    if(this.draw) {
      this.draw.moved=Math.hypot(e.clientX-this.draw.x,e.clientY-this.draw.y)>5;
      if(this.draw.moved) {
        const p=this.drawPoint(hit);this.view.showGhost(p,this.draw.parent,this.element);
        this.view.updateOverlays(this.selection,hit===this.draw.parent?null:hit,this.draw.parent);
      }
      e.stopImmediatePropagation();return;
    }
    super.move(e);
    if(!this.locked&&this.tool==='add'&&hit!==null)this.view.showGhost(point(this.getModel().atoms[hit]),null,this.element);
    if(!this.locked&&this.tool==='bond'&&!this.bondKind&&hit!==null) {
      const target=this.growthTarget(hit);this.view.showGhost(target.position,target.parent,this.element);
    }
    if(!this.locked&&this.tool==='fragment'&&this.fragment) {
      if(e.buttons){this.clearFragmentPreview();return;}
      const position=hit===null?this.view.raycaster.ray.intersectPlane(new Plane().setFromNormalAndCoplanarPoint(this.view.camera.getWorldDirection(new Vector3()),this.view.centroid()),new Vector3()):null;
      const key=[hit,position?.x,position?.y,position?.z].join(':');
      if(this.fragmentHover===key)return;
      this.fragmentHover=key;
      try {this.view.showFragmentPreview(this.fragmentPlan(hit,position).preview);}
      catch {this.clearFragmentPreview();}
    }
  }
  up(e) {
    const hit=this.view.pick(e);
    if(this.area){finishArea(this,e);return;}
    if(this.rotateDrag) {
      const d=this.rotateDrag;this.rotateDrag=null;this.view.controls.enabled=true;
      if(d.moved){this.push(d.snapshot);this.getModel().smiles='';this.onChange(this.getModel(),false);}
      if(this.view.renderer.domElement.hasPointerCapture(e.pointerId))this.view.renderer.domElement.releasePointerCapture(e.pointerId);
      this.update();e.stopImmediatePropagation();return;
    }
    if(e.button===2&&this.rightStart) {
      const s=this.rightStart;this.rightStart=null;
      if(this.tool==='add'&&Math.hypot(e.clientX-s.x,e.clientY-s.y)<5) {
        if(hit!==null)this.delete([hit]);else if(s.bond!==null)this.mutate(m=>m.bonds.splice(s.bond,1),false);
      }
      return;
    }
    if(this.bondStart) {
      const s=this.bondStart;this.bondStart=null;this.view.controls.enabled=true;
      if(Math.hypot(e.clientX-s.x,e.clientY-s.y)<5) {
        if(this.tool==='delete')this.mutate(m=>m.bonds.splice(s.bond,1),false);
        else {const b=this.getModel().bonds[s.bond];this.setBond(b.a,b.b);}
      }
      e.stopImmediatePropagation();return;
    }
    if(this.draw&&this.draw.pointerId===e.pointerId) {
      const d=this.draw,p=this.drawPoint(hit);this.draw=null;
      this.view.controls.enabled=true;this.view.showGhost(null,null,this.element);
      if(this.view.renderer.domElement.hasPointerCapture(e.pointerId))this.view.renderer.domElement.releasePointerCapture(e.pointerId);
      e.stopImmediatePropagation();
      if(!d.moved) {
        if(d.parent!==null)this.grow(d.parent);
        else if(d.bond!==null){const b=this.getModel().bonds[d.bond];this.setBond(b.a,b.b);}
        else if(p)this.mutate(m=>{this.selection=[m.atoms.length];m.atoms.push({el:this.element,x:p.x,y:p.y,z:p.z});});
      } else if(d.parent!==null&&hit!==null&&hit!==d.parent)this.setBond(d.parent,hit);
      else if(d.parent!==null&&p)this.mutate(m=>{
        const b=m.atoms.length;m.atoms.push({el:this.element,x:p.x,y:p.y,z:p.z});m.bonds.push({a:d.parent,b,order:this.bondOrder});this.selection=[b];
      });
      else if(d.origin&&p)this.mutate(m=>{
        const a=m.atoms.length,dir=p.clone().sub(d.origin).normalize();
        const end=d.origin.clone().addScaledVector(dir,idealLength(this.element,this.element,this.bondOrder));
        m.atoms.push({el:this.element,x:d.origin.x,y:d.origin.y,z:d.origin.z},{el:this.element,x:end.x,y:end.y,z:end.z});
        m.bonds.push({a,b:a+1,order:this.bondOrder});this.selection=[a+1];
      });
      this.update();return;
    }
    if(['add','fragment'].includes(this.tool)&&this.start) {
      const s=this.start;this.start=null;
      if(this.locked||e.button!==0||s.pointerId!==e.pointerId||s.moved||Math.hypot(e.clientX-s.x,e.clientY-s.y)>5)return;
      if(this.tool==='fragment') {
        if(hit!==s.hit||s.bond!==null)return;
        const plane=new Plane().setFromNormalAndCoplanarPoint(this.view.camera.getWorldDirection(new Vector3()),this.view.centroid());
        const position=this.view.raycaster.ray.intersectPlane(plane,new Vector3());
        try {this.insertFragment(this.fragment,{anchor:hit,position});}
        catch(error){this.toast(error.message,'error');}
        return;
      }
      if(hit!==null&&hit===s.hit)this.replaceAtom(hit);
      else if(hit===null&&s.hit===null) {
        if(s.bond!==null){const b=this.getModel().bonds[s.bond];this.setBond(b.a,b.b);}
        else {
          const plane=new Plane().setFromNormalAndCoplanarPoint(this.view.camera.getWorldDirection(new Vector3()),this.view.centroid());
          const p=this.view.raycaster.ray.intersectPlane(plane,new Vector3());if(p)this.add(null,p);
        }
      }
      return;
    }
    if(this.tool==='select'&&e.shiftKey&&hit!==null&&this.start&&Math.hypot(e.clientX-this.start.x,e.clientY-this.start.y)<5) {
      this.start=null;this.select(hit,true);return;
    }
    super.up(e);
  }
  cancel() {
    this.clearFragmentPreview();
    const gesture=this.area||this.rotateDrag;
    if(this.rotateDrag){const snapshot=this.rotateDrag.snapshot;this.rotateDrag=null;this.selection=snapshot.selection;this.onChange(snapshot.model,true);}
    this.area=null;if(this.areaSvg)this.areaSvg.style.display='none';
    if(gesture&&this.view.renderer.domElement.hasPointerCapture(gesture.pointerId))this.view.renderer.domElement.releasePointerCapture(gesture.pointerId);
    const d=this.draw;this.draw=null;this.bondStart=null;this.rightStart=null;
    if(d) {
      const c=this.view.renderer.domElement;if(c.hasPointerCapture(d.pointerId))c.releasePointerCapture(d.pointerId);
      this.view.showGhost(null,null,this.element);
    }
    super.cancel();
  }
  clearFragmentPreview() {
    this.fragmentHover=null;this.view.showFragmentPreview?.(null);
  }
  chooseFragment(fragment) {
    this.fragment=fragment;this.setTool('fragment');
    this.view.renderer.domElement.style.cursor='crosshair';
  }
  fragmentPlan(anchor,position=null,fragment=this.fragment) {
    return planFragment(this.getModel(),fragment,{root:fragment.root??0,mode:fragment.mode||'replace',anchor,position,hydrogens:this.autoHydrogens});
  }
  insertFragment(fragment=this.fragment,{anchor=this.selection.length===1?this.selection[0]:null,position=null}={}) {
    if(this.locked)return;
    const result=this.fragmentPlan(anchor,position,fragment);
    this.clearFragmentPreview();
    this.mutate(m=>{Object.assign(m,result.model);this.selection=result.selection;},false);
    this.view.fit(true);
  }
}
