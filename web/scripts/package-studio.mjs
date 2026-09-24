import {build} from 'vite';
import {readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import {resolve} from 'node:path';
process.chdir(resolve(import.meta.dirname,'..'));
const out='.studio-build',target=resolve('../src/alder/assets');
const cleanShaderIndent=text=>text.replace(/^[ \t]+/gm,indent=>indent.replace(/\t/g,'  ')).replace(/[ \t]+$/gm,'');
await build({configFile:false,build:{outDir:out,emptyOutDir:true,copyPublicDir:false,lib:{entry:'src/studio.js',name:'StudioBuilder',formats:['iife'],fileName:()=> 'builder.js'}}});
const js=cleanShaderIndent(await readFile(`${out}/builder.js`,'utf8')).replace(/<\/script/gi,'<\\/script');
const packed=JSON.stringify({js:(await readFile('public/vendor/rdkit/RDKit_minimal.js')).toString('base64'),wasm:(await readFile('public/vendor/rdkit/RDKit_minimal.wasm')).toString('base64')});
let licenses='Studio builder third-party notices\n';
for(const [name,path] of [['Three.js','node_modules/three/LICENSE'],['LZ-String','node_modules/lz-string/LICENSE'],['RDKit','public/vendor/rdkit/LICENSE'],['three-gpu-pathtracer','node_modules/three-gpu-pathtracer/LICENSE'],['three-mesh-bvh','node_modules/three-mesh-bvh/LICENSE'],['Mediabunny','node_modules/mediabunny/LICENSE']])licenses+=`\n${name}\n${await readFile(path,'utf8')}\n`;
const html=`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'self' qrc: data:; script-src 'self' 'unsafe-inline' 'unsafe-eval' qrc: data:; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; worker-src blob:"><style>html,body,#viewport{margin:0;width:100%;height:100%;overflow:hidden;background:white;font:14px sans-serif;color:#52645a}#viewport{position:absolute;touch-action:none}canvas{display:block;width:100%;height:100%}#empty{position:absolute;top:40%;left:15%;right:15%;text-align:center;pointer-events:none;line-height:1.8}#empty b{display:block;font-size:22px;color:#26382d}#help{position:absolute;bottom:14px;left:18px;font-size:12px;pointer-events:none}[hidden]{display:none!important}</style><script src="qrc:///qtwebchannel/qwebchannel.js"></script></head><body><div id="viewport"></div><div id="empty"><b>Build your next molecule</b>Paste a SMILES string, copy a calculated geometry,<br>or choose an element and click to place an atom.</div><div id="help">Choose element → click atom to replace · Attach atom to grow · Middle-drag to rotate · Right-drag to pan · Scroll to zoom</div><script type="application/json" id="alder-rdkit">${packed}</script><script>${js}</script></body></html>`;
await mkdir(target,{recursive:true});await writeFile(resolve(target,'builder.html'),html);await writeFile(resolve(target,'builder-LICENSES.txt'),licenses);await rm(out,{recursive:true});console.log(`Built offline Studio builder: ${(Buffer.byteLength(html)/1024/1024).toFixed(1)} MiB`);

await build({configFile:false,build:{outDir:out,emptyOutDir:true,copyPublicDir:false,lib:{entry:'src/studio-calculation.js',name:'StudioCalculation',formats:['iife'],fileName:()=> 'viewer.js'}}});
await writeFile(resolve(target,'viewer.js'),cleanShaderIndent(await readFile(`${out}/viewer.js`,'utf8')));
await rm(out,{recursive:true});
