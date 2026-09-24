import * as THREE from 'three';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { MolecularView } from './viewer.js';
import { CPK } from './chemistry.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import '../../src/alder/assets/appearance.js';

// Keep the editing overlays/instancing, but use Studio's shared figure proportions.
export class StudioView extends MolecularView {
  constructor(host) {
    super(host);
    this.appearance = {preset:'Studio', outline:true, ao:false, orthographic:true};
    this.scene.environment = null;
    this.scene.background = new THREE.Color('white');
    this.renderer.toneMapping = THREE.NoToneMapping;
    this.scene.children.filter(o=>o.isLight).forEach(o=>this.scene.remove(o));
    this.scene.add(new THREE.AmbientLight(0xffffff, 1.7));
    this.keyLight = new THREE.DirectionalLight(0xffffff, 2.1);
    this.scene.add(this.keyLight, this.keyLight.target);
    this.outlineMeshes = [];
    this.outlineCylinder = new THREE.CylinderGeometry(1,1,1,20,1,true);
    this.controls.dispose();
    this.controls = new TrackballControls(this.camera, this.renderer.domElement);
    this.controls.staticMoving = true;
    this.controls.keys = []; // Editor shortcuts must not change the mouse action.
    this.controls.rotateSpeed = 2.4;
    this.controls.mouseButtons.MIDDLE = THREE.MOUSE.ROTATE;
    this.fogOptions={enabled:false,strength:.35,offset:0};
    this.installDepthCue();
    for(const event of ['change','start','end'])this.controls.addEventListener(event,()=>this.invalidate());
    // Trackball accumulates input until update(); wake only for pointer gestures.
    this.renderer.domElement.addEventListener('pointermove',e=>{if(e.buttons&&this.controls.enabled)this.invalidate();});
    this.observer.disconnect();
    this.resize = () => {
      const w=Math.max(1,host.clientWidth), h=Math.max(1,host.clientHeight);
      this.renderer.setSize(w,h);
      this.camera.aspect=w/h;
      if(this.camera.isOrthographicCamera) {
        const half=(this.camera.top-this.camera.bottom)/2;
        this.camera.left=-half*w/h;this.camera.right=half*w/h;
      }
      this.camera.updateProjectionMatrix();
      this.composer?.setSize(w,h);
      this.controls.handleResize();
      this.invalidate();
    };
    this.observer = new ResizeObserver(this.resize);this.observer.observe(host);
    this.setAppearance(this.appearance);
  }
  setMeasurementCount(count) {
    this.measurementCount=[2,3,4].includes(count)?count:0;
    this.updateOverlays([],null);
  }
  reportMeasurement(measurement,text,ids) {
    const state=JSON.stringify({count:this.measurementCount||0,
      indices:ids.slice(), atoms:ids.map(i=>`${this.model.atoms[i].el}${i+1}`),
      kind:measurement?.kind||'',text});
    if(state!==this.lastMeasurementState){this.lastMeasurementState=state;this.onMeasurementChange?.(state);}
  }
  updateControls(delta) {
    if(this.controls.autoRotate) {
      const axis=this.camera.up.clone().normalize(),q=new THREE.Quaternion().setFromAxisAngle(axis,delta*0.08);
      this.camera.position.sub(this.controls.target).applyQuaternion(q).add(this.controls.target);
    }
    this.controls.update();
  }
  render() {
    // RenderPass clears before applying scene.background; reset the GL clear alpha.
    this.renderer.setClearColor(0x000000,0);
    this.updateFog();
    this.keyLight.position.copy(this.camera.position).add(new THREE.Vector3(-3,5,2));
    this.keyLight.target.position.copy(this.controls.target);
    if(this.appearance.ao && this.composer) {
      const uniforms=this.aoPass.ssaoMaterial.uniforms;
      uniforms.cameraProjectionMatrix.value.copy(this.camera.projectionMatrix);
      uniforms.cameraInverseProjectionMatrix.value.copy(this.camera.projectionMatrixInverse);
      this.composer.render();
    } else super.render();
  }
  setStyle(options) {
    if(options.style) this.style.representation=({'Ball and stick':'ball','Stick':'sticks','Space filling':'space'})[options.style];
    for(const key of ['hydrogens','labels','size','spin','background'])
      if(options[key]!==undefined)this.style[key]=options[key];
    this.controls.autoRotate=this.style.spin;
    this.scene.background=this.style.background==='transparent'?null:new THREE.Color(this.style.background==='dark'?'#202824':'#ffffff');
    this.host.style.background=this.style.background==='transparent'?'repeating-conic-gradient(#e2e5e3 0% 25%,#fff 0% 50%) 0 / 20px 20px':this.style.background==='dark'?'#202824':'#ffffff';
    const geometryChanged=options.style!==undefined || ['hydrogens','labels','size'].some(k=>options[k]!==undefined);
    if(geometryChanged)this.syncModel(this.model);
    this.updateOverlays();this.invalidate();
  }
  setFog(options) {
    if(options.enabled!==undefined)this.fogOptions.enabled=!!options.enabled;
    for(const [key,min,max] of [['strength',0,1],['offset',-1,2]])
      if(Number.isFinite(options[key]))this.fogOptions[key]=THREE.MathUtils.clamp(options[key],min,max);
    if(!this.fogOptions.enabled)this.setDepthCuePick(false,false);
    this.updateFog();this.invalidate();
  }
  setDepthCuePick(enabled,notify=true) {
    if(enabled&&!this.depthPicking)this.depthCursor=this.renderer.domElement.style.cursor;
    if(enabled)this.renderer.domElement.style.cursor='crosshair';
    else if(this.depthPicking)this.renderer.domElement.style.cursor=this.depthCursor||'grab';
    this.depthPicking=!!enabled;
    if(notify)this.onFogChange?.({...this.fogOptions,armed:this.depthPicking});
  }
  fogBounds(camera=this.camera) {
    camera.updateMatrixWorld();
    let near=Infinity,far=-Infinity;
    const p=new THREE.Vector3();
    this.model.atoms.forEach((a,i)=>{
      if(!this.visible(i))return;
      const depth=-p.set(a.x,a.y,a.z).applyMatrix4(camera.matrixWorldInverse).z,r=this.radius(a);
      near=Math.min(near,depth-r);far=Math.max(far,depth+r);
    });
    return Number.isFinite(near)?{near,span:Math.max(1,far-near)}:{near:0,span:1};
  }
  updateFog(camera=this.camera) {
    if(!this.fogOptions?.enabled||!this.fogOptions.strength){this.scene.fog=null;return;}
    const {near,span}=this.fogBounds(camera),start=near+span*this.fogOptions.offset;
    this.scene.fog??=new THREE.Fog();
    this.scene.fog.color.set(this.style.background==='dark'?'#202824':'#ffffff');
    this.scene.fog.near=start;this.scene.fog.far=start+span/this.fogOptions.strength;
  }
  installDepthCue() {
    const canvas=this.renderer.domElement;
    const finish=()=>{
      const drag=this.fogDrag;if(!drag)return;
      this.fogDrag=null;this.controls.enabled=drag.enabled;this.controls.autoRotate=drag.spin;
      if(canvas.hasPointerCapture(drag.id))canvas.releasePointerCapture(drag.id);
      this.invalidate();
    };
    this.cancelDepthCue=()=>{finish();this.setDepthCuePick(false);};
    canvas.addEventListener('pointerdown',e=>{
      if(!this.active||!this.controls.enabled)return;
      const hit=this.pick(e),pick=e.button===0&&this.depthPicking&&hit!==null;
      const drag=e.button===2&&!e.shiftKey&&this.fogOptions.enabled&&hit===null&&this.pickBond(e)===null;
      if(!pick&&!drag)return;
      this.fogDrag={id:e.pointerId,x:e.clientX,y:e.clientY,hit,pick,offset:this.fogOptions.offset,
        enabled:this.controls.enabled,spin:this.controls.autoRotate};
      this.controls.enabled=false;this.controls.autoRotate=false;
      canvas.setPointerCapture(e.pointerId);e.preventDefault();e.stopImmediatePropagation();
    },true);
    canvas.addEventListener('pointermove',e=>{
      const d=this.fogDrag;if(!d||d.id!==e.pointerId)return;
      if(!d.pick){
        this.setFog({offset:d.offset+(e.clientX-d.x)*3/Math.max(1,canvas.clientWidth)});
        this.onFogChange?.({...this.fogOptions,armed:this.depthPicking});
      }
      e.preventDefault();e.stopImmediatePropagation();
    },true);
    canvas.addEventListener('pointerup',e=>{
      const d=this.fogDrag;if(!d||d.id!==e.pointerId)return;
      if(d.pick&&Math.hypot(e.clientX-d.x,e.clientY-d.y)<5&&this.pick(e)===d.hit){
        const a=this.model.atoms[d.hit],{near,span}=this.fogBounds();
        const depth=-new THREE.Vector3(a.x,a.y,a.z).applyMatrix4(this.camera.matrixWorldInverse).z;
        this.setFog({enabled:true,offset:(depth-near)/span});this.setDepthCuePick(false);
      }
      finish();e.preventDefault();e.stopImmediatePropagation();
    },true);
    for(const type of ['pointercancel','lostpointercapture'])canvas.addEventListener(type,finish,true);
    canvas.addEventListener('contextmenu',e=>e.preventDefault());
    window.addEventListener('keydown',e=>{
      if(e.key==='Escape'&&(this.depthPicking||this.fogDrag)){
        this.cancelDepthCue();e.preventDefault();e.stopImmediatePropagation();
      }
    },true);
  }
  applyFogToImage(canvas,camera) {
    this.updateFog(camera);
    if(!this.scene.fog)return;
    // One raster depth pass applies the same cue to ray-traced pixels. Source-atop
    // preserves the ray tracer's alpha, including antialiased transparent edges.
    if(!this.fogMaterial){
      this.fogMaterial=new THREE.MeshBasicMaterial({side:THREE.DoubleSide});
      this.fogMaterial.onBeforeCompile=shader=>{
        shader.fragmentShader=shader.fragmentShader.replace('#include <fog_fragment>',
          '#ifdef USE_FOG\ngl_FragColor.rgb = fogColor;\ngl_FragColor.a = smoothstep(fogNear, fogFar, vFogDepth);\n#endif');
      };
    }
    this.fogMaterial.color.copy(this.scene.fog.color);
    const hidden=[this.overlays,this.labels,...this.outlineMeshes],visible=hidden.map(o=>o.visible);
    const background=this.scene.background,override=this.scene.overrideMaterial;
    try {
      hidden.forEach(o=>o.visible=false);this.scene.background=null;this.scene.overrideMaterial=this.fogMaterial;
      this.renderer.setSize(canvas.width,canvas.height,false);this.renderer.setClearColor(0,0);
      this.renderer.render(this.scene,camera);
      const ctx=canvas.getContext('2d');ctx.save();ctx.globalCompositeOperation='source-atop';
      ctx.drawImage(this.renderer.domElement,0,0);ctx.restore();
    } finally {
      this.scene.background=background;this.scene.overrideMaterial=override;
      hidden.forEach((o,i)=>o.visible=visible[i]);this.resize();
    }
  }
  cameraState() {
    return {up:this.camera.up.toArray(),position:this.camera.position.toArray(),target:this.controls.target.toArray(),quaternion:this.camera.quaternion.toArray(),zoom:this.camera.zoom,
      half:this.camera.isOrthographicCamera?this.camera.top:null};
  }
  restoreCamera(state) {
    if(state.up)this.camera.up.fromArray(state.up);
    this.camera.position.fromArray(state.position);this.camera.quaternion.fromArray(state.quaternion);this.controls.target.fromArray(state.target);this.camera.zoom=state.zoom;
    if(state.half && this.camera.isOrthographicCamera){this.camera.top=state.half;this.camera.bottom=-state.half;}
    this.resize();this.controls.update();this.invalidate();
  }
  showFragmentPreview(model) {
    if(!model&&!this.fragmentPreview)return;
    if(this.fragmentPreview) {
      for(const mesh of this.fragmentPreview.children){mesh.material.dispose();mesh.dispose();}
      this.overlays.remove(this.fragmentPreview);this.fragmentPreview=null;
    }
    if(model) {
      const group=new THREE.Group(),visible=a=>this.style.hydrogens||a.el!=='H';
      const atoms=model.atoms.filter(a=>visible(a)&&!a.previewExisting),segments=[];
      if(this.style.representation!=='space')for(const b of model.bonds) {
        const a=model.atoms[b.a],c=model.atoms[b.b];if(!visible(a)||!visible(c))continue;
        const start=new THREE.Vector3(a.x,a.y,a.z),end=new THREE.Vector3(c.x,c.y,c.z),dir=end.clone().sub(start),length=dir.length();
        if(length<1e-6)continue;
        dir.normalize();
        const offset=dir.clone().cross(Math.abs(dir.y)>.9?new THREE.Vector3(1,0,0):new THREE.Vector3(0,1,0)).normalize();
        const q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),dir);
        for(const d of b.order===2?[-.16,.16]:b.order===3?[-.22,0,.22]:[0])for(const [fraction,atom] of [[.25,a],[.75,c]])
          segments.push({p:start.clone().lerp(end,fraction).addScaledVector(offset,d),q,length:length/2,color:this.bondColor()||this.color(atom)});
      }
      const material=()=>new THREE.MeshPhysicalMaterial({roughness:.3,transparent:true,opacity:.42,depthWrite:false});
      const spheres=new THREE.InstancedMesh(this.sphereGeometry,material(),atoms.length),bonds=new THREE.InstancedMesh(this.cylinderGeometry,material(),segments.length),dummy=new THREE.Object3D();
      atoms.forEach((a,i)=>{dummy.position.set(a.x,a.y,a.z);dummy.quaternion.identity();dummy.scale.setScalar(this.radius(a));dummy.updateMatrix();spheres.setMatrixAt(i,dummy.matrix);spheres.setColorAt(i,new THREE.Color(a.junction?'#149447':this.color(a)));});
      segments.forEach((s,i)=>{dummy.position.copy(s.p);dummy.quaternion.copy(s.q);dummy.scale.set(this.bondRadius(),s.length,this.bondRadius());dummy.updateMatrix();bonds.setMatrixAt(i,dummy.matrix);bonds.setColorAt(i,new THREE.Color(s.color));});
      for(const mesh of [spheres,bonds]){mesh.computeBoundingSphere();mesh.renderOrder=3;group.add(mesh);}
      this.fragmentPreview=group;this.overlays.add(group);
    }
    this.invalidate();
  }
  capture({width=this.host.clientWidth,height=this.host.clientHeight,samples=1,transparent=false}={}) {
    const rw=width*samples,rh=height*samples,gl=this.renderer.getContext();
    const limit=gl.getParameter(gl.MAX_RENDERBUFFER_SIZE);
    if(Math.max(rw,rh)>limit || rw*rh>24000000)throw Error(`Requested ${rw} × ${rh} render exceeds this renderer’s ${limit}px / 24 megapixel limit. Reduce the size or select native resolution.`);
    const background=this.scene.background,overlays=this.overlays.visible;
    const aspect=this.camera.aspect,left=this.camera.left,right=this.camera.right;
    try {
      this.scene.background=transparent?null:background;
      this.overlays.visible=false;
      this.renderer.setSize(rw,rh,false);this.composer?.setSize(rw,rh);
      if(this.camera.isOrthographicCamera){this.camera.left=-this.camera.top*width/height;this.camera.right=-this.camera.left;}
      else this.camera.aspect=width/height;
      this.camera.updateProjectionMatrix();this.render();
      const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
      const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
      ctx.drawImage(this.renderer.domElement,0,0,width,height);
      return canvas;
    } finally {
      this.scene.background=background;this.overlays.visible=overlays;
      this.camera.aspect=aspect;this.camera.left=left;this.camera.right=right;
      this.resize();this.invalidate();
    }
  }

  get preset() { return MoleculeAppearance.settings(this.appearance?.preset || 'Studio'); }
  radius(a) {
    if(this.style.representation==='sticks') return this.preset.bondRadius;
    const r=MoleculeAppearance.radii[a.el] ?? 1.6;
    return r*(this.style.representation==='space' ? 1 : a.el==='H' ? this.preset.hydrogenScale : this.preset.scale)*this.style.size;
  }
  color(a) { return a.structureColor || this.preset.colors[a.el] || CPK[a.el] || '#d9d9d9'; }
  bondRadius() { return this.preset.bondRadius; }
  bondColor(a) { return a?.structureColor || this.preset.bondColor; }
  bondAxis(dir,bond) {
    // Keep ring double bonds in the ring plane instead of hiding one behind the other.
    const {atoms,bonds}=this.model;
    for(const endpoint of [bond.a,bond.b]) {
      const adjacent=bonds.filter(b=>b!==bond&&(b.a===endpoint||b.b===endpoint))
        .map(b=>b.a===endpoint?b.b:b.a).sort((a,b)=>(atoms[a].el==='H')-(atoms[b].el==='H'));
      for(const j of adjacent) {
        const a=atoms[endpoint],p=atoms[j],v=new THREE.Vector3(p.x-a.x,p.y-a.y,p.z-a.z);
        const normal=dir.clone().cross(v);
        if(normal.lengthSq()>1e-6)return dir.clone().cross(normal.normalize()).normalize();
      }
    }
    const normal=new THREE.Vector3(0,0,1);
    if(Math.abs(dir.dot(normal))>.9)normal.set(0,1,0);
    return dir.clone().cross(normal).normalize();
  }
  material() { return new THREE.MeshPhongMaterial({shininess:28,specular:0x333333}); }
  setAppearance(options) {
    Object.assign(this.appearance,options);
    const orthographic=this.appearance.orthographic;
    if(!!this.camera.isOrthographicCamera !== orthographic) {
      const old=this.camera, aspect=Math.max(1,this.host.clientWidth)/Math.max(1,this.host.clientHeight);
      const half=old.isOrthographicCamera ? old.top/old.zoom : old.position.distanceTo(this.controls.target)*Math.tan(THREE.MathUtils.degToRad(19));
      this.camera=orthographic ? new THREE.OrthographicCamera(-half*aspect,half*aspect,half,-half,0.05,5000) : new THREE.PerspectiveCamera(38,aspect,0.05,5000);
      this.camera.position.copy(old.position);this.camera.quaternion.copy(old.quaternion);this.camera.up.copy(old.up);
      if(!orthographic)this.camera.position.copy(this.controls.target).add(old.position.clone().sub(this.controls.target).normalize().multiplyScalar(half/Math.tan(THREE.MathUtils.degToRad(19))));
      this.controls.object=this.camera;this.controls.update();
      if(this.aoPass)this.aoPass.camera=this.camera;
      if(this.renderPass)this.renderPass.camera=this.camera;
    }
    if(this.appearance.ao && !this.composer) {
      this.composer=new EffectComposer(this.renderer);
      this.aoPass=new SSAOPass(this.scene,this.camera,this.host.clientWidth,this.host.clientHeight);
      this.aoPass.kernelRadius=8;this.aoPass.minDistance=0.001;this.aoPass.maxDistance=0.04;
      this.outputPass=new OutputPass();
      this.renderPass=new RenderPass(this.scene,this.camera);
      this.composer.addPass(this.renderPass);this.composer.addPass(this.aoPass);this.composer.addPass(this.outputPass);
    }
    if(this.aoPass)for(const material of [this.aoPass.ssaoMaterial,this.aoPass.depthRenderMaterial]) {
      material.defines.PERSPECTIVE_CAMERA=orthographic?0:1;material.needsUpdate=true;
    }
    this.resize();this.syncModel(this.model);this.updateOverlays();
  }
  fit(preserveDirection=false) {
    const direction=this.camera.position.clone().sub(this.controls.target).normalize(),up=this.camera.up.clone();
    if(!this.camera.isOrthographicCamera)super.fit();
    else {
    const c=this.centroid();let r=this.model.atoms.length?1:3;
    for(const a of this.model.atoms)r=Math.max(r,new THREE.Vector3(a.x,a.y,a.z).distanceTo(c)+this.radius(a));
    const aspect=Math.max(1,this.host.clientWidth)/Math.max(1,this.host.clientHeight), half=r*1.15/Math.min(1,aspect);
    Object.assign(this.camera,{left:-half*aspect,right:half*aspect,top:half,bottom:-half,zoom:1});
    this.camera.position.copy(c).add(new THREE.Vector3(0,0,Math.max(16,r*4)));
    this.camera.up.set(0,1,0);this.controls.target.copy(c);this.camera.lookAt(c);this.camera.updateProjectionMatrix();this.controls.update();
    }
    if(preserveDirection) {
      const distance=this.camera.position.distanceTo(this.controls.target);
      this.camera.position.copy(this.controls.target).addScaledVector(direction,distance);
      this.camera.up.copy(up);this.camera.lookAt(this.controls.target);this.controls.update();this.invalidate();
    }
  }
  syncModel(model, options={}) {
    super.syncModel(model,options);
    if(!this.outlineMeshes)return;
    if(options.full!==false) {
      for(const m of this.outlineMeshes){this.scene.remove(m);m.material.dispose();m.dispose();}
      this.outlineMeshes=[this.atomMesh,this.bondMesh].map((source,index)=>{
        const m=new THREE.InstancedMesh(index===1?this.outlineCylinder:source.geometry,new THREE.MeshBasicMaterial({color:'#252a25',side:THREE.BackSide}),source.count);
        this.scene.add(m);return m;
      });
    }
    const matrix=new THREE.Matrix4(),p=new THREE.Vector3(),q=new THREE.Quaternion(),s=new THREE.Vector3();
    [this.atomMesh,this.bondMesh].forEach((source,index)=>{
      const outline=this.outlineMeshes[index];outline.visible=this.appearance.outline;
      const changed=new Set(options.changed||[]);
      for(let i=0;i<source.count;i++) {
        if(options.full===false) {
          const b=index===1?this.model.bonds[this.halves[i].bond]:null;
          if(index===0?!changed.has(i):!changed.has(b.a)&&!changed.has(b.b))continue;
        }
        source.getMatrixAt(i,matrix);matrix.decompose(p,q,s);
        if(s.x>0){s.x+=0.012;s.z+=0.012;if(index===0)s.y+=0.012;}
        matrix.compose(p,q,s);outline.setMatrixAt(i,matrix);
      }
      outline.instanceMatrix.needsUpdate=true;outline.computeBoundingSphere();
    });
  }
  pickBond(event) {
    this.pick(event);this.bondMesh?.updateMatrixWorld();
    if(this.style.representation==='space' || !this.bondMesh)return null;
    const hit=this.raycaster.intersectObject(this.bondMesh).find(h=>{
      const b=this.model.bonds[this.halves[h.instanceId].bond];return this.visible(b.a)&&this.visible(b.b);
    });
    return hit ? this.halves[hit.instanceId].bond : null;
  }
  dispose() { this.fogMaterial?.dispose();this.aoPass?.ssaoMaterial.dispose();this.aoPass?.dispose();this.outputPass?.dispose();this.composer?.dispose();super.dispose(); }
}
