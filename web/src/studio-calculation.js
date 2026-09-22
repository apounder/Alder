// Calculation and figure adapter. All pixels are rendered by the same StudioView as Build.
import * as THREE from 'three';
import {StudioView} from './studio-view.js';
import {parseXYZ,validateModel} from './chemistry.js';
let viewer,bridge,volume=null,colorVolume=null,cubeVisible=false,shapes=[],vdwSurface=null;
let surfaceOptions={isoval:0.03,opacity:0.75,signed:true,mode:'orbital',min:-0.05,max:0.05,scale:1,gradient:'esp',legend:true};
let commandQueue=Promise.resolve(),vibration=null;
window.sceneState={atoms:0,surfaces:0,mapped:false,ready:false,error:null,exportSize:null};
function palette(options) {
  return options.gradient === 'nci' ? ['#245cdd','#52c85d','#d93936'] : ['#de4237','#fafafa','#3262d8'];
}

function gradient(options) {
  const colors = palette(options).map(hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)));
  return {
    range:()=>[options.min,options.max],
    valueToHex(value) {
      if(!Number.isFinite(value)) return 0xaaaaaa;
      let t;
      if(options.min < 0 && options.max > 0) {
        t = value <= 0 ? 0.5*(value-options.min)/-options.min : 0.5+0.5*value/options.max;
      } else t = (value-options.min)/(options.max-options.min);
      t = Math.max(0,Math.min(1,t))*2;
      const i=Math.min(1,Math.floor(t)), f=t-i;
      const c=colors[i].map((v,k)=>Math.round(v*(1-f)+colors[i+1][k]*f));
      return (c[0]<<16)|(c[1]<<8)|c[2];
    }
  };
}

function sampledField(data, scale) {
  // Trilinear sampling avoids blocky colors and supports rotated cube grids.
  const sampled=Object.create(data);
  sampled.getVal=(x,y,z)=>{
    if(data.matrix) {
      if(!data.inversematrix) data.getIndex(x,y,z);
      const p=new $3Dmol.Vector3(x,y,z).applyMatrix4(data.inversematrix);
      [x,y,z]=[p.x,p.y,p.z];
    } else [x,y,z]=[(x-data.origin.x)/data.unit.x,(y-data.origin.y)/data.unit.y,(z-data.origin.z)/data.unit.z];
    const coords=[x,y,z], sizes=[data.size.x,data.size.y,data.size.z];
    if(coords.some((v,i)=>v < -1e-4 || v > sizes[i]-1+1e-4)) return NaN;
    const base=coords.map((v,i)=>Math.max(0,Math.min(sizes[i]-1,Math.floor(v))));
    const frac=coords.map((v,i)=>Math.max(0,Math.min(1,v-base[i])));
    let result=0;
    for(let a=0;a<2;a++) for(let b=0;b<2;b++) for(let c=0;c<2;c++) {
      const i=Math.min(base[0]+a,sizes[0]-1), j=Math.min(base[1]+b,sizes[1]-1), k=Math.min(base[2]+c,sizes[2]-1);
      result += data.data[(i*sizes[1]+j)*sizes[2]+k] *
        (a ? frac[0] : 1-frac[0])*(b ? frac[1] : 1-frac[1])*(c ? frac[2] : 1-frac[2]);
    }
    return result*scale;
  };
  return sampled;
}

function legendTitle(options) {
  if(options.mode.startsWith('esp')) return 'Electrostatic potential / a.u.';
  if(['nci','igm'].includes(options.mode)) return 'sign(λ₂)ρ / a.u.';
  return 'Color field / native units';
}

function legend(canvas, options, transparent=false) {
  const ctx=canvas.getContext('2d'), w=canvas.width, h=canvas.height;
  const fs=Math.max(12,Math.round(w/90)), bw=Math.round(w*0.24), bh=Math.max(9,Math.round(h*0.016));
  const x=w-bw-fs*2, y=h-fs*3-bh;
  ctx.fillStyle=transparent ? 'rgba(255,255,255,0.82)' : '#ffffff';
  ctx.fillRect(x-fs,y-fs*2,bw+fs*2,bh+fs*4);
  const stops=palette(options), g=ctx.createLinearGradient(x,0,x+bw,0);
  const mid=options.min<0 && options.max>0 ? -options.min/(options.max-options.min) : 0.5;
  g.addColorStop(0,stops[0]); g.addColorStop(mid,stops[1]); g.addColorStop(1,stops[2]);
  ctx.fillStyle=g;ctx.fillRect(x,y,bw,bh);
  ctx.fillStyle='#344238';ctx.font=`${fs}px sans-serif`;ctx.textAlign='left';
  ctx.fillText(legendTitle(options),x,y-fs*0.65);
  ctx.fillText(String(options.min),x,y+bh+fs*1.35);
  ctx.textAlign='right';ctx.fillText(String(options.max),x+bw,y+bh+fs*1.35);
  if(options.min<0 && options.max>0) {ctx.textAlign='center';ctx.fillText('0',x+bw*mid,y+bh+fs*1.35);}
}

function updateLegend() {
  const host=document.getElementById('colorScale');
  host.hidden=!(cubeVisible && colorVolume && surfaceOptions.legend);
  if(!host.hidden) {
    const c=document.createElement('canvas');c.width=900;c.height=290;
    legend(c,surfaceOptions); host.replaceChildren(c);
  }
}


function makeSurface(position,index,colors,options,color) {
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(position,3));
  geometry.setIndex(Array.from(index));geometry.computeVertexNormals();
  if(colors) {
    const values=new Float32Array(position.length),ramp=gradient(options),sample=sampledField(colors,options.scale),c=new THREE.Color();
    for(let i=0;i<position.length;i+=3) {
      c.setHex(ramp.valueToHex(sample.getVal(position[i],position[i+1],position[i+2])));
      c.toArray(values,i);
    }
    geometry.setAttribute('color',new THREE.BufferAttribute(values,3));
  }
  const material=new THREE.MeshPhongMaterial({color:colors?'white':color,vertexColors:!!colors,shininess:28,specular:0x333333,side:THREE.DoubleSide,transparent:options.opacity<1,opacity:options.opacity,depthWrite:options.opacity===1});
  return new THREE.Mesh(geometry,material);
}
function isosurface(field,colors,options,isoval,color) {
  // Reuse the bundled CPU marching cubes only; no second WebGL renderer/context.
  const shape=new $3Dmol.GLShape({color});
  shape.addIsosurface(field,{isoval,color,smoothness:1});
  const geo=shape.finalize(),group=new THREE.Group();
  for(const g of geo.geometryGroups)if(g.vertices && g.faceidx)
    group.add(makeSurface(g.vertexArray.slice(0,g.vertices*3),g.faceArray.slice(0,g.faceidx),colors,options,color));
  geo.dispose();return group;
}
function vdw(colors,options) {
  const atoms=viewer.model.atoms.map((a,serial)=>({...a,elem:a.el,serial})),ids=atoms.map((_,i)=>i);
  const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
  for(const a of atoms)for(const [i,k] of ['x','y','z'].entries()){min[i]=Math.min(min[i],a[k]);max[i]=Math.max(max[i],a[k]);}
  const ps=new $3Dmol.ProteinSurface();
  ps.initparm([min,max],false,(max[0]-min[0])*(max[1]-min[1])*(max[2]-min[2]));
  ps.fillvoxels(atoms,ids);ps.buildboundary();ps.marchingcube(1);
  const {vertices,faces}=ps.getFacesAndVertices(ids);
  return makeSurface(vertices.flatMap(p=>[p.x,p.y,p.z]),faces,colors,options,'#5598c7');
}
function clearSurfaces() {
  for(const shape of shapes) {
    viewer.scene.remove(shape);
    shape.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});
  }
  shapes=[];vdwSurface=null;
}
async function surfaces() {
  clearSurfaces();
  if(volume && cubeVisible) {
    if(surfaceOptions.mode==='esp_vdw' && viewer.model.atoms.length) {
      vdwSurface=vdw(colorVolume,surfaceOptions);shapes.push(vdwSurface);
    } else {
      const o=surfaceOptions;
      if(o.fieldMin<o.isoval && o.isoval<o.fieldMax)shapes.push(isosurface(volume,colorVolume,o,o.isoval,'#5598c7'));
      if(o.signed && o.mode==='orbital' && o.fieldMin<-o.isoval && -o.isoval<o.fieldMax)shapes.push(isosurface(volume,colorVolume,o,-o.isoval,'#e28b45'));
    }
    for(const shape of shapes)viewer.scene.add(shape);
  }
  window.sceneState.surfaces=shapes.length;window.sceneState.mapped=!!(cubeVisible&&colorVolume);
  updateLegend();viewer.invalidate();
}
function exportFigure(cmd) {
  const canvas=viewer.capture(cmd),samples=cmd.samples||1;
  window.sceneState.exportRenderSize=[canvas.width*samples,canvas.height*samples];
  window.sceneState.exportSize=[canvas.width,canvas.height];
  if(cubeVisible&&colorVolume&&surfaceOptions.legend)legend(canvas,surfaceOptions,cmd.transparent);
  bridge.imageReady(canvas.toDataURL('image/png'));
}
function poseVibration() {
  if(!vibration)return;
  const shift=Math.sin(vibration.phase)*vibration.amplitude;
  viewer.model.atoms.forEach((a,i)=>{for(const [k,axis] of ['x','y','z'].entries())a[axis]=vibration.base[i][k]+vibration.vectors[i][k]*shift;});
  viewer.syncModel(viewer.model,{full:false,changed:viewer.model.atoms.map((_,i)=>i)});
  viewer.updateOverlays();
}
function stopVibration() {
  if(vibration){vibration.phase=0;poseVibration();vibration=null;}
  window.sceneState.vibration=null;viewer.invalidate();
}
function vibrationSettings(cmd) {
  if(!vibration)return;
  for(const key of ['amplitude','rate'])if(Number.isFinite(cmd[key]))vibration[key]=Math.max(0,Math.min(key==='amplitude'?1:3,cmd[key]));
  if(cmd.playing!==undefined)vibration.playing=!!cmd.playing;
  if(cmd.reset)vibration.phase=0;
  window.sceneState.vibration={mode:vibration.mode,playing:vibration.playing,amplitude:vibration.amplitude,rate:vibration.rate};
  poseVibration();viewer.invalidate();
}
async function startVibration(cmd) {
  const model=parseXYZ(cmd.xyz),vectors=cmd.vectors||model.atoms.map(()=>[0,0,0]);
  if(vectors.length!==model.atoms.length||vectors.some(v=>v.length!==3||v.some(x=>!Number.isFinite(x))))throw Error('Invalid vibrational displacement vectors');
  const max=Math.max(...vectors.map(v=>Math.hypot(...v)),1e-12);
  stopVibration();cubeVisible=false;await surfaces();
  viewer.syncModel(model);viewer.updateOverlays([],null);
  vibration={mode:cmd.mode,base:model.atoms.map(a=>[a.x,a.y,a.z]),vectors:vectors.map(v=>v.map(x=>x/max)),phase:0,amplitude:.3,rate:.7,playing:false};
  window.sceneState.atoms=model.atoms.length;
  vibrationSettings(cmd);
}
async function handleCommand(cmd) {
  if(cmd.type==='vibration'){await startVibration(cmd);return;}
  if(cmd.type==='vibrationSettings'){vibrationSettings(cmd);return;}
  if(cmd.type==='vibrationStop'){stopVibration();return;}
  if(cmd.type==='geometry') {
    stopVibration();
    const model=cmd.model?validateModel(cmd.model):cmd.xyz?.startsWith('0\n')?{atoms:[],bonds:[]}:parseXYZ(cmd.xyz);
    // Reuse GPU buffers for trajectory frames with unchanged topology.
    const same=model.atoms.length===viewer.model.atoms.length && model.atoms.every((a,i)=>a.el===viewer.model.atoms[i].el) && JSON.stringify(model.bonds)===JSON.stringify(viewer.model.bonds);
    viewer.syncModel(model,{full:!same,changed:model.atoms.map((_,i)=>i)});
    viewer.updateOverlays([] ,null);window.sceneState.atoms=model.atoms.length;
    document.getElementById('hint').hidden=!!model.atoms.length;
    if(cmd.fit)viewer.fit();
    if(cubeVisible!==cmd.surface || surfaceOptions.mode==='esp_vdw'){cubeVisible=cmd.surface;await surfaces();}
  } else if(cmd.type==='cube') {
    volume=cmd.text?new $3Dmol.VolumeData(cmd.text,'cube'):null;
    colorVolume=cmd.mapping?new $3Dmol.VolumeData(cmd.mapping,'cube'):null;
    surfaceOptions=cmd.options||surfaceOptions;cubeVisible=!!cmd.text&&cmd.visible!==false;await surfaces();
  } else if(cmd.type==='surface') {surfaceOptions=cmd.options;cubeVisible=cmd.visible;await surfaces();}
  else if(cmd.type==='style')viewer.setStyle(cmd);
  else if(cmd.type==='appearance')viewer.setAppearance(cmd);
  else if(cmd.type==='fit')viewer.fit();
  else if(cmd.type==='visibility')viewer.setActive(cmd.visible);
  else if(cmd.type==='export')exportFigure(cmd);
  window.sceneState.error=null;
}
new QWebChannel(qt.webChannelTransport,channel=>{
  bridge=channel.objects.bridge;
  try {
    viewer=new StudioView(document.getElementById('viewer'));viewer.syncModel({atoms:[],bonds:[]});viewer.fit();
    viewer.isAnimating=()=>!!vibration?.playing;
    viewer.onFrame=(now,delta)=>{if(vibration?.playing){vibration.phase=(vibration.phase+delta*vibration.rate*2*Math.PI)%(2*Math.PI);poseVibration();}};
    window.calculationApp={view:viewer,get vibration(){return vibration;},get surfaceOptions(){return surfaceOptions;},get shapes(){return shapes;},get colorVolume(){return colorVolume;},get vdwSurface(){return vdwSurface;},sampledField,gradient};
    // Measurement and hover use the same overlays and picking as Build, without mutations.
    const canvas=viewer.renderer.domElement;let start;
    canvas.addEventListener('pointerdown',e=>{start={x:e.clientX,y:e.clientY};});
    canvas.addEventListener('pointermove',e=>{const hit=viewer.pick(e);if(hit!==viewer.hoverIndex)viewer.updateOverlays(viewer.selection,hit);});
    canvas.addEventListener('pointerleave',()=>viewer.updateOverlays(viewer.selection,null));
    canvas.addEventListener('pointerup',e=>{
      if(e.button!==0||!start||Math.hypot(e.clientX-start.x,e.clientY-start.y)>5)return;
      const hit=viewer.pick(e);if(hit===null)return;
      let ids=[...viewer.selection];const k=ids.indexOf(hit);
      if(k>=0)ids.splice(k,1);else{if(ids.length>=4)ids=[];ids.push(hit);}
      viewer.updateOverlays(ids,hit);
    });
    window.addEventListener('keydown',e=>{if(e.key==='Escape')viewer.updateOverlays([],null);});
    bridge.command.connect(json=>{commandQueue=commandQueue.then(()=>handleCommand(JSON.parse(json))).catch(error=>{window.sceneState.error=String(error);bridge.reportError(String(error));});});
    window.sceneState.ready=true;bridge.ready();
  } catch(error){bridge.reportError(String(error));}
});
