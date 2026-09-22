import {build} from 'vite';
import {readFile,writeFile,rm} from 'node:fs/promises';
import {resolve} from 'node:path';
process.chdir(resolve(import.meta.dirname,'..'));
const out='.sketch-build',target=resolve('../src/molecule_studio/assets');
await build({configFile:false,resolve:{alias:{events:resolve('node_modules/events/events.js'),buffer:resolve('node_modules/buffer/index.js')}},define:{global:'globalThis','process.env.NODE_ENV':'"production"'},build:{commonjsOptions:{transformMixedEsModules:true},outDir:out,emptyOutDir:true,copyPublicDir:false,
  lib:{entry:'src/sketch.js',name:'StudioSketch',formats:['iife'],fileName:()=> 'sketch.js'},rollupOptions:{onwarn(warn,handler){if(warn.code!=='MODULE_LEVEL_DIRECTIVE')handler(warn);},output:{inlineDynamicImports:true,banner:'var process={env:{NODE_ENV:"production"},browser:true,nextTick:(fn,...args)=>queueMicrotask(()=>fn(...args))};'}}}}).catch(e=>{console.error(e.message);process.exit(1);});
const js=(await readFile(`${out}/sketch.js`,'utf8')).replace(/<\/script/gi,'<\\/script');
const css=await readFile(`${out}/molstudio-web.css`,'utf8');
await writeFile(resolve(target,'sketch.html'),`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'self' qrc: data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' qrc: data: blob:; worker-src blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'none'"><style>${css}
html,body,#root{margin:0;width:100%;height:100%;overflow:hidden;background:white;font:13px system-ui}#root{position:absolute;inset:0}#loading{position:absolute;inset:40% 15% auto;text-align:center;font:15px system-ui;color:#607568}#message{position:absolute;bottom:4px;left:70px;right:75px;color:#a44320;background:#fff9ee;font:12px system-ui;z-index:100;pointer-events:none}#message:empty{display:none}.locked #root{pointer-events:none;opacity:.6}.locked:after{content:'Generating 3D geometry…';position:absolute;top:45%;left:30%;background:white;padding:20px;border:1px solid #d8e4db;border-radius:8px;color:#14793b;z-index:200}button{font-family:system-ui!important}</style><script src="qrc:///qtwebchannel/qwebchannel.js"></script></head><body><div id="root"></div><div id="loading">Loading the local 2D structure editor…</div><div id="message" role="alert"></div><script>${js}</script></body></html>`);
let licenses='2D structure editor third-party notices\nKetcher Core, React, Standalone — Copyright 2021 EPAM Systems\nLicensed under Apache-2.0 (text below with Indigo).\n';
for(const pkg of ['ketcher-react','ketcher-core','ketcher-standalone','react','react-dom','indigo-ketcher']) {
  for(const name of ['LICENSE','LICENSE.txt','LICENSE.md'])try {licenses+=`\n${pkg}\n${await readFile(`node_modules/${pkg}/${name}`,'utf8')}\n`;break;}catch{}
}
await writeFile(resolve(target,'sketch-LICENSES.txt'),licenses);
await rm(out,{recursive:true});console.log('Bundled offline Ketcher 2D editor.');
