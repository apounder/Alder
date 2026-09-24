import { chromium } from 'playwright';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
try {
 await page.goto(process.env.PREVIEW_URL||'http://127.0.0.1:4173');await page.waitForFunction(()=>window.alder?.model.atoms.length===21);
 assert.equal(await page.evaluate(()=>!!window.initRDKitModule),false);
 await page.screenshot({path:'test-results/production.png'});
 const result=await page.evaluate(async()=>{
  const candidate={name:'Large-model responsiveness',atoms:Array.from({length:350},(_,i)=>({el:'C',x:(i%10)*2,y:Math.floor(i/10)%7*2,z:Math.floor(i/70)*2})),bonds:[]};
  alder.load(candidate);const before=JSON.stringify(alder.model),messages=[];let frames=0,running=true;
  const observer=new MutationObserver(()=>messages.push(document.querySelector('#toasts').textContent));observer.observe(document.querySelector('#toasts'),{subtree:true,childList:true,characterData:true});
  const frame=()=>{if(running){frames++;requestAnimationFrame(frame);}};requestAnimationFrame(frame);
  await alder.editor.tidy();running=false;observer.disconnect();const hasProgress=messages.some(s=>/Relaxing geometry… \d+%/.test(s)),changed=JSON.stringify(alder.model)!==before;alder.editor.undo();return {frames,hasProgress,changed,restored:JSON.stringify(alder.model)===before};
 });
 assert.ok(result.frames>1);assert.ok(result.hasProgress);assert.ok(result.changed);assert.ok(result.restored);assert.deepEqual(errors,[]);console.log('PASS production bundle, no-WASM initial render, large Tidy progress, UI animation frames, exact undo; zero console errors',result);
} finally {await browser.close();}
