import {Vector3, Quaternion} from 'three';
import {point} from './placement.js';

export function insidePolygon(x,y,points) {
  let inside=false;
  for(let i=0,j=points.length-1;i<points.length;j=i++) {
    const a=points[i],b=points[j];
    if((a.y>y)!==(b.y>y) && x<(b.x-a.x)*(y-a.y)/(b.y-a.y)+a.x)inside=!inside;
  }
  return inside;
}
export function startArea(editor,e) {
  const view=editor.view,canvas=view.renderer.domElement;
  editor.area={tool:editor.tool,pointerId:e.pointerId,points:[{x:e.clientX,y:e.clientY}]};
  view.controls.enabled=false;canvas.setPointerCapture(e.pointerId);
  if(!editor.areaSvg) {
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.style.cssText='position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:5';
    const path=document.createElementNS(svg.namespaceURI,'path');
    path.setAttribute('fill','rgba(24,145,67,.10)');path.setAttribute('stroke','#189143');path.setAttribute('stroke-width','1.5');path.setAttribute('stroke-dasharray','5 3');
    svg.append(path);canvas.parentElement.append(svg);editor.areaSvg=svg;
  }
  editor.areaSvg.style.display='';e.stopImmediatePropagation();
}
export function moveArea(editor,e) {
  const a=editor.area,p={x:e.clientX,y:e.clientY};
  if(a.tool==='rect')a.points=[a.points[0],p];
  else if(a.points.length<2048)a.points.push(p);
  const rect=editor.view.renderer.domElement.getBoundingClientRect();
  let pts=a.points;
  if(a.tool==='rect') {const [p,q=p]=pts;pts=[p,{x:q.x,y:p.y},q,{x:p.x,y:q.y}];}
  editor.areaSvg.firstChild.setAttribute('d',pts.map((p,i)=>`${i?'L':'M'}${p.x-rect.left},${p.y-rect.top}`).join(' ')+' Z');
  e.stopImmediatePropagation();
}
export function finishArea(editor,e) {
  const a=editor.area,view=editor.view,rect=view.renderer.domElement.getBoundingClientRect();
  let points=a.points;
  if(a.tool==='rect') {const [p,q=p]=points;points=[p,{x:q.x,y:p.y},q,{x:p.x,y:q.y}];}
  view.camera.updateMatrixWorld();
  const ids=editor.getModel().atoms.flatMap((a,i)=>{
    if(!view.visible(i))return [];
    const p=point(a).project(view.camera);
    return p.z>=-1&&p.z<=1&&insidePolygon(rect.left+(p.x+1)*rect.width/2,rect.top+(1-p.y)*rect.height/2,points)?[i]:[];
  });
  editor.selection=e.shiftKey?[...new Set([...editor.selection,...ids])]:ids;
  editor.area=null;editor.areaSvg.style.display='none';view.controls.enabled=true;
  if(view.renderer.domElement.hasPointerCapture(e.pointerId))view.renderer.domElement.releasePointerCapture(e.pointerId);
  editor.update();e.stopImmediatePropagation();
}
export function rotateSelection(editor,e) {
  const d=editor.rotateDrag,view=editor.view;
  const right=new Vector3(1,0,0).applyQuaternion(view.camera.quaternion),up=new Vector3(0,1,0).applyQuaternion(view.camera.quaternion);
  const rotation=new Quaternion().setFromAxisAngle(up,(e.clientX-d.x)*.01).multiply(new Quaternion().setFromAxisAngle(right,(e.clientY-d.y)*.01));
  d.moved=Math.hypot(e.clientX-d.x,e.clientY-d.y)>2;
  for(const [i,start] of d.positions)Object.assign(editor.getModel().atoms[i],start.clone().sub(d.center).applyQuaternion(rotation).add(d.center));
  view.syncModel(editor.getModel(),{full:false,changed:d.positions.map(([i])=>i)});editor.update();e.stopImmediatePropagation();
}
