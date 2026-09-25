// Run after npm run package:studio. Exercise the actual offline desktop bundle.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';

const root=resolve(import.meta.dirname,'../..'),output=resolve(root,'web/test-results/figures');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:500,height:400}}),errors=[];
page.setDefaultTimeout(240000);
page.on('pageerror',error=>errors.push(error.message));
page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
try {
  await page.setContent('<style>#viewer{width:480px;height:360px}</style><div id="viewer"></div><div id="hint"></div><div id="colorScale"></div>');
  await page.evaluate(()=>{
    window.qt={webChannelTransport:{}};
    const bridge={command:{connect:fn=>window.command=fn},ready(){},measurementChanged(){},fogChanged(){},
      reportError:message=>window.failure=message,exportProgress(){},imageReady:data=>window.exported=data,exportFinished:status=>window.exportStatus=status};
    window.QWebChannel=function(_,callback){callback({objects:{bridge}});};
  });
  await page.addScriptTag({content:await readFile(resolve(root,'src/alder/assets/viewer.js'),'utf8')});
  await page.waitForFunction(()=>window.calculationApp||window.failure);
  assert.equal(await page.evaluate(()=>window.failure),undefined);
  const send=command=>page.evaluate(cmd=>window.command(JSON.stringify(cmd)),command);
  const snapshot=()=>page.evaluate(()=>JSON.stringify({model:calculationApp.view.model,camera:calculationApp.view.cameraState()}));
  const capture=async(name,{engine='raytrace',transparent=false}={})=>{
    const before=await snapshot();
    await page.evaluate(()=>{window.exported=null;window.failure=null;});
    await send({type:'export',width:160,height:120,engine,transparent,raySamples:4,samples:1});
    await page.waitForFunction(()=>window.exported||window.failure);
    assert.equal(await page.evaluate(()=>window.failure),null);
    const data=await page.evaluate(()=>window.exported);
    await writeFile(resolve(output,name+'.png'),Buffer.from(data.split(',')[1],'base64'));
    const metrics=await page.evaluate(async()=>{
      const image=new Image();image.src=exported;await image.decode();
      const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
      const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);
      const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
      let red=0,blue=0,solid=0,partial=0;
      for(let i=0;i<pixels.length;i+=4){
        const [r,g,b,a]=pixels.slice(i,i+4);
        if(a>240){solid++;red+=r>g+40;blue+=b>r+40;}
        partial+=a>0&&a<240;
      }
      return {red,blue,solid,partial,corner:Array.from(pixels.slice(0,4))};
    });
    assert.equal(await snapshot(),before,'Export must preserve geometry and camera');
    assert.ok(metrics.solid>100,JSON.stringify(metrics));
    console.log(name,metrics);
    return metrics;
  };
  const model={atoms:[{el:'O',x:-1.2,y:0,z:0},{el:'N',x:1.2,y:0,z:0}],bonds:[]};
  await send({type:'geometry',model,fit:true,surface:false});
  await page.waitForFunction(()=>calculationApp.view.model.atoms.length===2);
  await send({type:'fog',enabled:true,strength:.35,offset:0});
  for(const transparent of [false,true]){
    const stats=await capture(transparent?'ray-fog-transparent':'ray-fog-white',{transparent});
    assert.ok(stats.red>100&&stats.blue>100,'Moderate fog must preserve atom colors');
    assert.deepEqual(stats.corner,transparent?[0,0,0,0]:[255,255,255,255]);
  }
  await send({type:'fog',enabled:false});
  await send({type:'appearance',orthographic:false});
  const perspective=await capture('ray-perspective');
  assert.ok(perspective.red>100&&perspective.blue>100);
  await send({type:'appearance',orthographic:true});
  const signatures=new Set();
  for(const [preset,style] of [['Flat','Ball and stick'],['Tube','Stick'],['Ball and tube','Ball and stick'],['Wire','Stick'],['vdW','Space filling']]){
    await send({type:'style',style});await send({type:'appearance',preset,outline:preset==='Flat',ao:false});
    await capture('preset-'+preset.replaceAll(' ','-'),{engine:'studio'});
    signatures.add(await page.evaluate(()=>window.exported));
  }
  assert.equal(signatures.size,5,'All presets must produce distinct figures');
  const water={atoms:[{el:'O',x:0,y:0,z:0},{el:'H',x:1,y:0,z:0},{el:'O',x:2.8,y:0,z:0}],bonds:[{a:0,b:1,order:1}]};
  await send({type:'style',style:'Ball and stick'});await send({type:'appearance',preset:'Studio'});
  await send({type:'geometry',model:water,fit:true,surface:false});
  await send({type:'figureAddons',nci:true,vdw:true,opacity:.18});await send({type:'fit'});
  await page.waitForFunction(()=>calculationApp.view.figureGroup.children.length===2);
  assert.ok(await page.evaluate(()=>calculationApp.view.contacts.some(c=>c.kind==='hydrogen')));
  const addons=await capture('ray-addons',{transparent:true});
  assert.ok(addons.partial>100,'Translucent vdW spheres must be included in ray tracing');
  const moved=structuredClone(water);moved.atoms[2].x=12;
  await send({type:'geometry',model:moved,fit:false,surface:false});
  await page.waitForFunction(()=>calculationApp.view.contacts.length===0);
  await send({type:'figureAddons',nci:false,vdw:false});
  await page.waitForFunction(()=>calculationApp.view.figureGroup.children.length===0);
  assert.deepEqual(await page.evaluate(()=>calculationApp.view.model.bonds),water.bonds);
  assert.deepEqual(errors,[]);
  console.log('PASS: packaged renderer, fog colors, backgrounds, projections, five presets, contact updates, ray-traced vdW overlays and exact export restoration.');
} finally {await browser.close();}
