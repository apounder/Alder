import {Output,StreamTarget,WebMOutputFormat,CanvasSource,Quality,canEncodeVideo} from 'mediabunny';
import {RayTraceExport,nextFrame,checkCancelled} from './raytrace.js';
const jobs=new WeakMap();
export function cancelExport(view) {const job=jobs.get(view);if(job){job.cancelled=true;job.abortWorker?.();}}

// The same image renderer serves Calculation, Figure, Build, and every movie frame.
export async function renderExport(view,cmd,bridge,{frame,decorate=()=>{},restore=()=>{}}={}) {
  if(jobs.has(view))throw Error('An export is already running.');
  const job={cancelled:false},active=view.active,enabled=view.controls.enabled;
  jobs.set(view,job);view.setActive(false);view.controls.enabled=false;
  let tracer,output;
  const progress=(fraction,message)=>bridge.exportProgress(Math.round(fraction*1000),message);
  try {
    const {width,height}=cmd;
    if(!Number.isInteger(width)||!Number.isInteger(height)||Math.min(width,height)<1)throw Error('Invalid export dimensions.');
    if(cmd.engine==='raytrace')tracer=new RayTraceExport(view,width,height,cmd.transparent,job);
    const capture=async callback=>{
      checkCancelled(job);await nextFrame();
      const canvas=tracer?await tracer.capture(Math.max(1,Math.min(1024,cmd.raySamples||64)),callback):view.capture(cmd);
      decorate(canvas);return canvas;
    };
    if(!cmd.video) {
      const canvas=await capture(progress);checkCancelled(job);
      bridge.imageReady(canvas.toDataURL('image/png'));return;
    }
    const {fps,count}=cmd.video;
    if(!frame||!Number.isInteger(count)||count<1||count>12000||!Number.isFinite(fps)||fps<1||fps>60)throw Error('Invalid movie duration (maximum 12,000 frames).');
    if(width*height>3840*2160)throw Error('Video export supports up to 3840 × 2160 pixels.');
    const quality=new Quality('high');let codec;
    for(const c of ['vp9','vp8'])if(await canEncodeVideo(c,{width,height,frameRate:fps,quality})){codec=c;break;}
    if(!codec)throw Error('This graphics runtime cannot encode WebM video. Update Molecule Studio or your graphics driver.');
    const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
    const ctx=canvas.getContext('2d');
    const target=new StreamTarget(new WritableStream({async write({data,position}) {
      for(let i=0;i<data.length;i+=49152) {
        checkCancelled(job);
        const text=btoa(String.fromCharCode(...data.subarray(i,i+49152)));
        const ok=await new Promise(resolve=>bridge.videoChunk(text,position+i,resolve));
        if(!ok)throw Error('Cannot write the video file. Check free space and file permissions.');
      }
    }}),{chunked:true,chunkSize:1048576});
    output=new Output({format:new WebMOutputFormat(),target});
    const source=new CanvasSource(canvas,{codec,quality});output.addVideoTrack(source,{frameRate:fps});
    await output.start();
    let image;
    for(let i=0;i<count;i++) {
      checkCancelled(job);frame(i);
      if(!image||cmd.video.kind==='vibration'||i%cmd.video.hold===0)image=await capture((f,message)=>progress((i+f)/count,`Frame ${i+1} / ${count} · ${message}`));
      ctx.fillStyle=view.style.background==='dark'?'#202824':'#fff';ctx.fillRect(0,0,width,height);ctx.drawImage(image,0,0);
      await source.add(i/fps,1/fps);progress((i+1)/count,`Encoded frame ${i+1} / ${count}`);
    }
    await output.finalize();checkCancelled(job);
    bridge.exportFinished('complete');
  } catch(error) {
    if(output&&output.state!=='finalized')await output.cancel().catch(()=>{});
    if(error.name==='AbortError')bridge.exportFinished('cancelled');else throw error;
  } finally {
    tracer?.dispose();restore();view.controls.enabled=enabled;view.setActive(active);jobs.delete(view);
  }
}
