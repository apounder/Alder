import {BufferGeometry,BufferAttribute} from 'three';
import {MeshBVH} from 'three-mesh-bvh';
self.onmessage=({data:{position,index,options}})=>{
  try {
    const geometry=new BufferGeometry();
    geometry.setAttribute('position',new BufferAttribute(position,3));
    if(index)geometry.setIndex(new BufferAttribute(index,1));
    const bvh=new MeshBVH(geometry,options),serialized=MeshBVH.serialize(bvh,{cloneBuffers:false});
    self.postMessage({serialized,position});
  } catch(error){self.postMessage({error:String(error)});}
};
