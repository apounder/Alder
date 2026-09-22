import * as THREE from 'three';
import {WebGLPathTracer,GradientEquirectTexture} from 'three-gpu-pathtracer';
import {MeshBVH} from 'three-mesh-bvh';
import BVHWorker from './raytrace-worker.js?worker&inline';

export const nextFrame=()=>new Promise(requestAnimationFrame);
export function checkCancelled(job){if(job.cancelled)throw new DOMException('Export cancelled','AbortError');}

// Expand GPU instances into one indexed geometry per source mesh, never one Mesh per atom.
async function flattened(source,job) {
  const g=source.geometry,p=g.attributes.position,n=g.attributes.normal,vc=g.attributes.color;
  const ids=[],instance=new THREE.Matrix4();
  for(let i=0;i<(source.isInstancedMesh?source.count:1);i++) {
    if(source.isInstancedMesh){source.getMatrixAt(i,instance);if(Math.abs(instance.determinant())<1e-12)continue;}
    ids.push(i);
  }
  const count=ids.length,vertices=p.count,indices=g.index?.count||vertices;
  if(!count)return null;
  if(count*indices/3>2000000)throw Error('Ray tracing is limited to two million triangles per mesh. Hide hydrogens or export a smaller structure.');
  const positions=new Float32Array(count*vertices*3),normals=new Float32Array(positions.length),colors=new Float32Array(positions.length);
  const index=new Uint32Array(count*indices),matrix=new THREE.Matrix4(),normal=new THREE.Matrix3(),v=new THREE.Vector3(),color=new THREE.Color();
  source.updateMatrixWorld(true);
  for(let i=0;i<count;i++) {
    if(i%24===0){checkCancelled(job);await nextFrame();}
    if(source.isInstancedMesh){source.getMatrixAt(ids[i],matrix);matrix.premultiply(source.matrixWorld);source.getColorAt(ids[i],color);}
    else {matrix.copy(source.matrixWorld);color.copy(source.material.color);}
    normal.getNormalMatrix(matrix);
    for(let j=0;j<vertices;j++) {
      const offset=(i*vertices+j)*3;
      v.fromBufferAttribute(p,j).applyMatrix4(matrix).toArray(positions,offset);
      v.fromBufferAttribute(n,j).applyNormalMatrix(normal).toArray(normals,offset);
      colors[offset]=color.r*(vc?vc.getX(j):1);colors[offset+1]=color.g*(vc?vc.getY(j):1);colors[offset+2]=color.b*(vc?vc.getZ(j):1);
    }
    for(let j=0;j<indices;j++)index[i*indices+j]=i*vertices+(g.index?g.index.getX(j):j);
  }
  const result=new THREE.BufferGeometry();
  for(const [name,array] of [['position',positions],['normal',normals],['color',colors]])result.setAttribute(name,new THREE.BufferAttribute(array,3));
  result.setIndex(new THREE.BufferAttribute(index,1));
  return result;
}

export class RayTraceExport {
  constructor(view,width,height,transparent,job) {
    this.view=view;this.job=job;this.width=width;this.height=height;
    this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
    const gl=this.renderer.getContext(),limit=gl.getParameter(gl.MAX_RENDERBUFFER_SIZE);
    if(width*height>16000000||Math.max(width,height)>limit){this.dispose();throw Error('Ray-traced exports exceed this GPU’s resolution limit. Reduce the image size.');}
    this.renderer.setPixelRatio(1);this.renderer.setSize(width,height,false);
    this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.renderer.toneMapping=THREE.ACESFilmicToneMapping;
    this.renderer.setClearColor(0,0);
    this.scene=new THREE.Scene();
    this.scene.background=transparent?null:(view.scene.background?.clone()||null);
    this.environment=new GradientEquirectTexture(128);
    this.environment.topColor.setRGB(1.5,1.5,1.5);this.environment.bottomColor.setRGB(.5,.55,.6);this.environment.update();
    this.scene.environment=this.environment;
    this.camera=view.camera.clone();
    if(this.camera.isOrthographicCamera){this.camera.left=-this.camera.top*width/height;this.camera.right=-this.camera.left;}
    else this.camera.aspect=width/height;
    this.camera.updateProjectionMatrix();this.camera.updateMatrixWorld();
    const light=new THREE.RectAreaLight(0xffffff,12,8,8);
    light.position.copy(this.camera.position).add(new THREE.Vector3(-4,6,3));light.lookAt(view.controls.target);this.scene.add(light);
    this.worker=new BVHWorker();
    this.tracer=new WebGLPathTracer(this.renderer);
    this.tracer.setBVHWorker({generate:(geometry,options)=>new Promise((resolve,reject)=>{
      const abort=()=>reject(new DOMException('Export cancelled','AbortError'));
      job.abortWorker=abort;
      this.worker.onerror=e=>{job.abortWorker=null;reject(Error(e.message||'Ray-tracing worker failed'));};
      this.worker.onmessage=({data})=>{
        job.abortWorker=null;
        if(data.error){reject(Error(data.error));return;}
        geometry.attributes.position.array=data.position;
        const bvh=MeshBVH.deserialize(data.serialized,geometry);
        resolve(bvh);
      };
      const {onProgress,...safeOptions}=options;
      this.worker.postMessage({position:geometry.attributes.position.array,index:geometry.index?.array,options:safeOptions});
    })});
    Object.assign(this.tracer,{renderDelay:0,minSamples:1,fadeDuration:0,rasterizeScene:false,dynamicLowRes:false,bounces:4});
    this.tracer.tiles.set(3,3);this.tracer.textureSize.set(256,256);
    this.meshes=[];
  }
  async capture(samples=64,progress=()=>{}) {
    checkCancelled(this.job);progress(0,'Preparing ray-traced scene');
    const sources=[this.view.atomMesh,this.view.bondMesh,this.view.arrowMesh];
    this.view.scene.traverseVisible(o=>{if(o.isMesh&&!o.isInstancedMesh&&!this.view.overlays.getObjectById(o.id))sources.push(o);});
    for(const m of this.meshes){this.scene.remove(m);m.geometry.dispose();m.material.dispose();}
    this.meshes=[];
    for(const source of sources.filter(s=>s?.visible&&(s.count??1)>0)) {
      const geometry=await flattened(source,this.job),original=source.material;
      if(!geometry)continue;
      const material=new THREE.MeshPhysicalMaterial({vertexColors:true,roughness:.3,metalness:0,clearcoat:.5,clearcoatRoughness:.25,
        side:original.side,transparent:original.transparent,opacity:original.opacity});
      const mesh=new THREE.Mesh(geometry,material);this.meshes.push(mesh);this.scene.add(mesh);
    }
    checkCancelled(this.job);await this.tracer.setSceneAsync(this.scene,this.camera);checkCancelled(this.job);
    const start=performance.now();let last=0;
    while(this.tracer.samples<samples) {
      checkCancelled(this.job);this.tracer.renderSample();
      if(performance.now()-last>150){progress(this.tracer.samples/samples,this.tracer.isCompiling?'Compiling ray-tracing shaders…':`Ray tracing · ${Math.floor(this.tracer.samples)} / ${samples} samples`);last=performance.now();}
      // The first shader compile can be slow on software/emulated graphics.
      // Keep yielding so progress and Cancel remain responsive during startup.
      if(!this.tracer.samples&&performance.now()-start>180000)throw Error('The GPU could not start path tracing. Try a smaller image or Studio rendering.');
      await nextFrame();
    }
    // Copy immediately after rendering; no preserveDrawingBuffer and no timing-dependent readback.
    this.tracer.renderSample();
    const canvas=document.createElement('canvas');canvas.width=this.width;canvas.height=this.height;
    const ctx=canvas.getContext('2d');ctx.drawImage(this.renderer.domElement,0,0);
    this.view.applyFogToImage(canvas,this.camera);
    for(const sprite of this.view.labels.children)if(sprite.visible) {
      const p=sprite.position.clone().project(this.camera),up=new THREE.Vector3(0,sprite.scale.y/2,0).applyQuaternion(this.camera.quaternion);
      const edge=sprite.position.clone().add(up).project(this.camera),h=Math.abs(edge.y-p.y)*this.height,w=h*sprite.scale.x/sprite.scale.y;
      let image=sprite.material.map.image;
      const fog=this.view.scene.fog;
      if(fog){
        const depth=-sprite.position.clone().applyMatrix4(this.camera.matrixWorldInverse).z;
        const tint=document.createElement('canvas');tint.width=image.width;tint.height=image.height;
        const paint=tint.getContext('2d');paint.drawImage(image,0,0);
        paint.globalCompositeOperation='source-atop';paint.globalAlpha=THREE.MathUtils.smoothstep(depth,fog.near,fog.far);
        paint.fillStyle=fog.color.getStyle();paint.fillRect(0,0,tint.width,tint.height);image=tint;
      }
      ctx.drawImage(image,(p.x+1)*this.width/2-w/2,(1-p.y)*this.height/2-h/2,w,h);
    }
    return canvas;
  }
  dispose() {
    if(this.job)this.job.abortWorker=null;
    this.worker?.terminate();this.tracer?.dispose();this.environment?.dispose();
    for(const mesh of this.meshes||[]){mesh.geometry.dispose();mesh.material.dispose();}
    this.renderer?.dispose();this.renderer?.forceContextLoss();
  }
}
