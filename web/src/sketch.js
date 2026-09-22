import React from 'react';
import {createRoot} from 'react-dom/client';
import {Editor} from 'ketcher-react';
import {StandaloneStructServiceProvider} from 'ketcher-standalone';
import 'ketcher-react/dist/index.css';

let connected=false;
let bridge, ketcher, loading=false, dirty=false, locked=false;
let queue=Promise.resolve();
const report=()=>bridge.stateChanged(JSON.stringify({ready:!!ketcher,dirty,atoms:ketcher?.editor.struct().atoms.size||0}));
function error(err) {
  const message=err?.message||String(err);
  document.querySelector('#message').textContent=message;
  bridge?.notice(message,'error');
}
async function command(cmd) {
  if(cmd.type==='lock') {locked=cmd.locked;document.body.classList.toggle('locked',locked);return;}
  if(cmd.type==='load') {
    loading=true;
    try {await ketcher.setMolecule(cmd.mol||'');dirty=!!cmd.dirty;document.querySelector('#message').textContent='';}
    finally {loading=false;report();}
  } else if(cmd.type==='saved') {dirty=false;report();}
  else if(cmd.type==='get') {
    if(ketcher.containsReaction())throw Error('Convert one molecule at a time. Reactions can still be saved from the 2D editor.');
    bridge.result(cmd.purpose,await ketcher.getMolfile('v2000'));
  } else if(cmd.type==='undo')ketcher.editor.undo();
  else if(cmd.type==='redo')ketcher.editor.redo();
  else if(cmd.type==='layout')await ketcher.layout();
  else if(cmd.type==='image') {
    const mol=await ketcher.getMolfile('v2000');
    const blob=await ketcher.generateImage(mol,{outputFormat:cmd.format||'png'});
    const reader=new FileReader();reader.onload=()=>bridge.result('image',reader.result);reader.readAsDataURL(blob);
  }
}
document.addEventListener('keydown',e=>{if(locked){e.preventDefault();e.stopImmediatePropagation();}},true);
new QWebChannel(qt.webChannelTransport,channel=>{
  bridge=channel.objects.sketch;
  const hidden=['recognize','miew','fullscreen','create-monomer'];
  createRoot(document.querySelector('#root')).render(React.createElement(Editor,{
    staticResourcesUrl:'.',structServiceProvider:new StandaloneStructServiceProvider(),
    disableMacromoleculesEditor:true,
    buttons:Object.fromEntries(hidden.map(name=>[name,{hidden:true}])),
    errorHandler:error,
    onInit(instance){
      if(ketcher===instance)return;
      ketcher=instance;window.ketcher=instance;
      instance.editor.subscribe('change',()=>{if(!loading){dirty=true;report();}});
      if(!connected){
        bridge.command.connect(text=>{queue=queue.then(()=>command(JSON.parse(text))).catch(error);});
        connected=true;bridge.ready();
      }
      window.sketchApp={command,get dirty(){return dirty;}};
      document.querySelector('#loading').hidden=true;
      report();
    }
  }));
});
window.addEventListener('unhandledrejection',e=>error(e.reason));
