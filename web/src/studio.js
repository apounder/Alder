// Desktop adapter: reuse the web editor engine, with Studio's native Qt controls.
import {renderExport,cancelExport} from './render-export.js';
import { StudioView } from './studio-view.js';
import { StudioEditor } from './editor/studio-editor.js';
import { adjustHydrogens } from './editor/hydrogens.js';
import { parseFile, parseXYZ, validateModel, formula } from './chemistry.js';
import { smilesToModel } from './rdkit.js';
import { writeXYZ, writeMOL, writePDB } from './io.js';
let bridge, view, editor, readonly=false, busy=false, revision=0, lastState='', measurement='';
let model={name:'Untitled molecule',smiles:'',atoms:[],bonds:[]};
let queue=Promise.resolve();
function notice(message,kind='info') {
  bridge.notice(message,kind);
  const dismiss=()=>{};dismiss.update=text=>bridge.notice(text,'info');return dismiss;
}
function report() {
  const state={ready:true,busy:busy||(editor.locked&&!readonly),name:model.name,atoms:model.atoms.length,bonds:model.bonds.length,formula:formula(model),tool:editor.tool,element:editor.element,bondOrder:editor.bondOrder,bondKind:editor.bondKind,autoHydrogens:editor.autoHydrogens,selection:editor.selection.length,undo:editor.undoStack.length,redo:editor.redoStack.length,spin:view.style.spin,measurement,revision,fragment:editor.fragment?.name,fragmentRoot:editor.fragment?.root,fragmentMode:editor.fragment?.mode};
  const text=JSON.stringify(state);window.builderState=state;
  if(text!==lastState){lastState=text;bridge.stateChanged(text);}
  const hint=readonly?'Select two atoms for figure bonds · Depth cue: click an atom · Right-drag empty space adjusts enabled fog':editor.tool==='fragment'?`${editor.fragment?.name || 'Fragment'} · Click atom to ${editor.fragment?.mode==='attach'?'attach by bond':'replace at green junction'} · Empty space places separately · Esc exits`:'Choose element → click atom to replace · Middle-drag: rotate · Right-drag: fog when enabled, otherwise pan · Shift + right-drag: pan';
  const help=document.querySelector('#help');if(help.textContent!==hint)help.textContent=hint;
  document.querySelector('#empty').hidden=!!model.atoms.length;
}
function changed(next,full=true) {
  model=next;revision++;if(full)view.syncModel(model);
  bridge.structureChanged(JSON.stringify(model));report();
}
function replace(next) {
  editor.cancel();editor.push();editor.selection=[];editor.armed=editor.hover=null;
  changed(validateModel(next));view.showGhost(null,null,editor.element);editor.setTool('select');view.fit();editor.update();
}
async function command(cmd) {
  if(cmd.type==='locked'){editor.locked=cmd.locked;editor.update();return;}
  if(cmd.type==='visibility') {if(!cmd.visible)editor.cancel();view.setActive(cmd.visible);return;}
  if(cmd.type==='readonly') {
    editor.cancel();readonly=cmd.enabled;editor.locked=readonly;
    view.overlays.visible=true;view.invalidate();return;
  }
  if(cmd.type==='figure') {const locked=editor.locked;editor.locked=true;try{await renderExport(view,cmd,bridge);}finally{editor.locked=locked;}return;}
  if(cmd.type==='style') {
    editor.clearFragmentPreview();
    if(!readonly&&editor.tool!=='select')cmd.spin=false;
    view.setStyle(cmd);editor.update();return;
  }
  if(cmd.type==='appearance'){editor.clearFragmentPreview();view.setAppearance(cmd);return;}
  if(cmd.type==='fog'){view.setFog(cmd);return;}
  if(cmd.type==='fogPick'){editor.cancel();view.setDepthCuePick(cmd.enabled);return;}
  if(cmd.type==='bondOrder'){editor.bondKind=['dative','ts'].includes(cmd.order)?cmd.order:null;editor.bondOrder=editor.bondKind?1:cmd.order;editor.setTool(editor.bondKind||editor.tool==='bond'?'bond':'add');return;}
  if(cmd.type==='annotation'){
    if(editor.selection.length!==2)throw Error('Select two atoms first; select the donor first for a dative arrow.');
    if(!['single','double','triple','dative','ts','remove'].includes(cmd.kind))throw Error('Unknown bond style.');
    const [a,b]=editor.selection;
    // Figure mode locks geometry editing, but explicit bond styling remains available.
    const locked=editor.locked;editor.locked=false;
    try {
      editor.mutate(m=>{
        m.bonds=m.bonds.filter(x=>!((x.a===a&&x.b===b)||(x.a===b&&x.b===a)));
        const order={single:1,double:2,triple:3}[cmd.kind];
        if(cmd.kind!=='remove')m.bonds.push({a,b,order:order||1,...(order?{}:{kind:cmd.kind})});
      },false);
    } finally {editor.locked=locked;}
    return;
  }
  if(cmd.type==='autoHydrogens'){editor.clearFragmentPreview();editor.autoHydrogens=cmd.enabled;editor.update();return;}
  if(cmd.type==='hydrogens'){editor.mutate(m=>{editor.selection=adjustHydrogens(m,editor.selection);},false);return;}
  if(cmd.type==='fragment'){
    const fragment={...cmd.fragment,model:validateModel(cmd.fragment.model)};
    editor.chooseFragment(fragment);
    if(cmd.action==='selected') {
      if(editor.selection.length!==1)throw Error('Select exactly one atom, or click an atom with the fragment tool.');
      editor.insertFragment(fragment,{anchor:editor.selection[0]});
    } else if(cmd.action==='separate')editor.insertFragment(fragment,{anchor:null});
    return;
  }
  if(cmd.type==='measure') {
    editor.cancel();
    if(!readonly)editor.setTool('select');
    editor.selection=[];editor.armed=editor.hover=null;
    view.setMeasurementCount(cmd.count);editor.update();return;
  }
  if(cmd.type==='fit'){view.fit();return;}
  if(cmd.type==='element'){editor.element=cmd.element;editor.setTool('add');return;}
  if(cmd.type==='tool'){editor.setTool(cmd.tool);return;}
  if(cmd.type==='new'){editor.new();return;}
  if(cmd.type==='undo'){editor.undo();return;}
  if(cmd.type==='redo'){editor.redo();return;}
  if(cmd.type==='delete'){editor.delete(editor.selection);return;}
  if(cmd.type==='escape'){
    if(view.depthPicking||view.fogDrag)view.cancelDepthCue();
    else {editor.selection=[];editor.armed=editor.hover=null;editor.setTool('select');editor.update();}
    return;
  }
  if(cmd.type==='apply'){editor.applyElement();return;}
  if(cmd.type==='tidy'){await editor.tidy();return;}
  if(cmd.type==='load'){replace(parseFile(cmd.text,cmd.name,notice));notice('Structure imported. Bond orders are inferred as single bonds for XYZ.');return;}
  if(cmd.type==='copy'){replace(parseXYZ(cmd.xyz,cmd.name));notice('Copied selected geometry. Inferred bonds are editable; energies and cube fields remain with the calculation.');return;}
  if(cmd.type==='restore'){replace(validateModel(cmd.model));return;}
  if(cmd.type==='smiles'){
    busy=true;editor.locked=true;report();notice('Building 3D geometry with the local chemistry engine…');
    try {const next=await smilesToModel(cmd.smiles,cmd.name||'Built molecule');editor.locked=false;replace(next);notice('Approximate 3D geometry generated.');}
    finally {busy=false;editor.locked=false;report();}return;
  }
  if(cmd.type==='export'){
    const writer={xyz:writeXYZ,mol:writeMOL,pdb:writePDB}[cmd.format];if(!writer)throw Error('Choose XYZ, MOL, or PDB.');
    bridge.textReady(writer(model));return;
  }
}
new QWebChannel(qt.webChannelTransport, channel=>{
  bridge=channel.objects.builder;
  try {
    view=new StudioView(document.querySelector('#viewport'));
    view.onFogChange=state=>bridge.fogChanged(JSON.stringify(state));
    view.onMeasurementChange=state=>bridge.measurementChanged(state);
    for(const overlay of [view.hover,view.halos,view.prospect,view.measureLine])overlay.material.color.set('#189143');
    editor=new StudioEditor(view,{getModel:()=>model,onChange:changed,onState:report,toast:notice});
    const canvas=view.renderer.domElement;let figureStart;
    canvas.addEventListener('pointerdown',e=>{if(readonly&&e.button===0)figureStart={x:e.clientX,y:e.clientY};});
    canvas.addEventListener('pointermove',e=>{if(readonly)view.updateOverlays(editor.selection,view.pick(e));});
    canvas.addEventListener('pointerleave',()=>{if(readonly)view.updateOverlays(editor.selection,null);});
    canvas.addEventListener('pointerup',e=>{
      const start=figureStart;figureStart=null;
      if(!readonly||e.button!==0||!start||Math.hypot(e.clientX-start.x,e.clientY-start.y)>5)return;
      const hit=view.pick(e);if(hit!==null)editor.select(hit,e.shiftKey);
    });
    view.onMeasurement=(m,text)=>{measurement=m?`${m.kind} · ${text}`:'';};
    window.addEventListener('keydown',e=>{if(e.key==='Escape'){command({type:'escape'});e.preventDefault();}});
    view.syncModel(model);view.fit();view.setActive(false);
    bridge.command.connect(text=>{if(JSON.parse(text).type==='exportCancel'){cancelExport(view);return;}queue=queue.then(()=>command(JSON.parse(text))).then(report).catch(error=>{notice(error.message||String(error),'error');bridge.reportError(String(error));busy=false;report();});});
    window.builderApp={view,editor,get model(){return model;},command};
    bridge.ready();report();
  } catch(error){bridge.reportError(String(error));}
});
