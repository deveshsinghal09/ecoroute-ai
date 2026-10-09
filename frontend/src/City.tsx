import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export default function City({ moving, zoom, reset }: {moving:boolean; zoom:number; reset:number}) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<{camera:THREE.PerspectiveCamera; controls:OrbitControls} | undefined>(undefined);
  const motion = useRef(moving); motion.current=moving;
  const dirty=useRef(true);
  useEffect(()=>{dirty.current=true;},[moving,zoom,reset]);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{
    const element=host.current!; let renderer:THREE.WebGLRenderer;
    try { renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'}); }
    catch {setFailed(true); return;}
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.5)); renderer.shadowMap.enabled=true;
    renderer.shadowMap.type=THREE.PCFShadowMap; renderer.shadowMap.autoUpdate=false; renderer.shadowMap.needsUpdate=true; renderer.toneMapping=THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure=.82; element.appendChild(renderer.domElement);
    renderer.domElement.setAttribute('aria-label','Illustrative 3D transit city. Drag to orbit; use the zoom buttons.');
    const scene=new THREE.Scene(); scene.background=new THREE.Color('#788c9e'); scene.fog=new THREE.Fog('#8d9ba7',145,320);
    // Atmospheric sky stays separate from the lighting environment: no external assets.
    const skyGeometry=new THREE.SphereGeometry(300,32,16);
    const skyMaterial=new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,
      vertexShader:`varying vec3 direction;void main(){direction=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader:`varying vec3 direction;
      float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
      float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
      void main(){vec3 d=normalize(direction);float h=max(d.y,0.);vec3 sky=mix(vec3(.52,.60,.68),vec3(.19,.32,.48),smoothstep(0.,.65,h));
      vec2 p=d.xz/max(.12,d.y+.15)*2.8;float n=0.;float a=.55;for(int i=0;i<4;i++){n+=a*noise(p);p=p*2.03+13.;a*=.5;}
      float cloud=smoothstep(.42,.72,n)*smoothstep(.015,.15,h);vec3 shade=mix(vec3(.50,.56,.63),vec3(.91,.91,.88),smoothstep(.4,.8,n));
      gl_FragColor=vec4(mix(sky,shade,cloud*.88),1.);}`});
    const sky=new THREE.Mesh(skyGeometry,skyMaterial);scene.add(sky);
    const camera=new THREE.PerspectiveCamera(40,1,0.5,450); camera.position.set(46,19,78);
    const controls=new OrbitControls(camera,renderer.domElement); controls.target.set(0,9,-12);
    controls.enableDamping=true; controls.enablePan=false; controls.minDistance=48; controls.maxDistance=130;
    controls.maxPolarAngle=Math.PI/2.22; controls.minPolarAngle=.65; controls.enableZoom=false;
    api.current={camera,controls};
    const pmrem=new THREE.PMREMGenerator(renderer), room=new RoomEnvironment(), env=pmrem.fromScene(room,.05);
    scene.environment=env.texture;
    const ambient=new THREE.HemisphereLight('#cad9ed','#374037',.85); scene.add(ambient);
    const sun=new THREE.DirectionalLight('#ffe0ba',2.8); sun.position.set(-40,65,20); sun.castShadow=true;
    sun.shadow.mapSize.set(2048,2048); Object.assign(sun.shadow.camera,{left:-90,right:90,top:70,bottom:-70,near:1,far:180});
    sun.shadow.bias=-.0005; sun.shadow.normalBias=.05; scene.add(sun);
    const materials:THREE.Material[]=[];
    const mat=(color:string,roughness=.5,metalness=.1)=>{const m=new THREE.MeshStandardMaterial({color,roughness,metalness}); materials.push(m); return m;};
    const ivory=mat('#bfc3c2'), white=mat('#e5e5df',.28,.18), silver=mat('#aab4b5',.24,.65), dark=mat('#1a2c37',.2,.7);
    const orange=mat('#ff732c',.25,.3), road=mat('#58656e',.24,.48), foliage=mat('#294530',.9), bark=mat('#666657');
    const warm=new THREE.MeshStandardMaterial({color:'#ffb96b',emissive:'#ff812b',emissiveIntensity:1.4});materials.push(warm);
    const boxGeometry=new THREE.BoxGeometry(1,1,1);
    function box(x:number,y:number,z:number,w:number,h:number,d:number,m:THREE.Material,parent:THREE.Object3D=scene) {
      const mesh=new THREE.Mesh(boxGeometry,m);mesh.position.set(x,y,z);mesh.scale.set(w,h,d);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;
    }
    box(0,-.4,0,320,.7,260,mat('#939fa7',.19,.5));
    box(0,.02,14,280,.12,13,road);box(0,.02,-24,280,.12,7,road);
    box(-31,.04,-4,8,.1,180,road);box(32,.04,-4,8,.1,180,road);
    for(let x=-130;x<130;x+=6) {box(x,.13,14,2,.025,.07,white);box(x,.13,-24,2,.025,.06,white);}
    for(const z of [10.7,11.9,16.3,17.5]) box(0,.18,z,260,.09,.12,silver);
    // Porcelain-and-glass skyline; deliberately illustrative, not Delhi building footprints.
    let seed=812; const random=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646;};
    const canvas=document.createElement('canvas');canvas.width=128;canvas.height=256;
    const ctx=canvas.getContext('2d')!;ctx.fillStyle='#354a59';ctx.fillRect(0,0,128,256);
    for(let y=0;y<256;y+=16) for(let x=0;x<128;x+=16){ctx.fillStyle=random()>.86?'#ffc477':random()>.5?'#7c97a6':'#243e50';ctx.fillRect(x+2,y+2,11,12);}
    const windowTexture=new THREE.CanvasTexture(canvas);windowTexture.colorSpace=THREE.SRGBColorSpace;
    const windows=new THREE.MeshStandardMaterial({map:windowTexture,color:'#b4c8d3',roughness:.25,metalness:.45});materials.push(windows);
    for(let row=0;row<5;row++)for(let col=0;col<13;col++){
      const x=(col-6)*12+(random()-.5)*3,z=-37-row*15; const height=6+random()*23+(row>2?5:0);
      const w=5+random()*4,d=6+random()*5;
      box(x,height/2,z,w,height,d,col%3===0?windows:ivory);
      box(x,height+.18,z,w+.35,.4,d+.35,white);
      if(col%3!==0){box(x,height/2,z+d/2+.025,w*.76,height*.87,.06,windows);for(let i=0;i<4;i++)box(x-w/2+(i+1)*w/5,height/2,z+d/2+.1,.2,height,.2,white);}
      if(col%4===0) box(x+w/2+.05,height/2,z,.12,height*.9,.3,orange);
      if(height>24)box(x+.8,height+1.8,z,2,3,2,silver);
    }
    // Floor bands, side glazing and rooftop equipment make the skyline readable in orbit.
    for(let x=-72;x<=72;x+=12){for(let y=4;y<22;y+=3)box(x,y,-36.4,5,.13,.15,silver);}
    // Low pavilions frame the transit interchange and keep a clear viewing corridor.
    for(const x of [-63,-48,-39,39,48,63])for(const z of [-9,1,35]){
      const h=4+random()*7;box(x,h/2,z,7,h,8,white);box(x,h*.6,z+4.02,5,h*.52,.09,windows);box(x,h+.2,z,7.6,.3,8.6,silver);
      box(x,.8,z+4.1,4,.22,.1,warm);
      box(x+3.52,h*.55,z,.08,h*.65,6,windows);
      for(let y=2;y<h;y+=2)box(x,y,z+4.12,7,.14,.14,silver);
      box(x-1,h+.65,z,2,.7,2,dark);box(x+1.8,h+.55,z-1,1.3,.5,2,silver);
    }
    box(0,.15,-5,29,.4,18,ivory);box(0,3.6,-5,25,6.5,13,dark);
    const glass=new THREE.MeshPhysicalMaterial({color:'#c4d4d9',metalness:.3,roughness:.12,transparent:true,opacity:.46});materials.push(glass);
    box(0,3.5,1.6,24,6,.08,glass);
    for(let x=-11;x<=11;x+=2.2){box(x,3.7,1.72,.16,7,.2,silver);box(x,3.3,1.42,.15,5,.15,warm);}
    for(let y=1;y<7;y+=2)box(0,y,1.8,25,.12,.2,silver);
    const extras:THREE.BufferGeometry[]=[];
    for(const z of [-12,-8,-4,0,2]){
      const pts=Array.from({length:33},(_,i)=>new THREE.Vector3(-14+i*28/32,6.3+3*Math.sin(i*Math.PI/32),z));
      const geo=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),40,.11,6,false);extras.push(geo);scene.add(new THREE.Mesh(geo,silver));
    }
    for(let x=-12;x<=12;x+=3)box(x,6.3+3*Math.sin((x+14)*Math.PI/28),-5,.09,.1,14,silver);
    box(0,5.4,1.94,26,.18,.16,warm);box(0,7.8,-5,7,.12,14,glass);
    // Solid curved glazing, with visible ribs instead of a floating wire frame.
    const roofVertices:number[]=[],roofIndices:number[]=[];
    for(let i=0;i<=32;i++){const x=-14+i*28/32,y=6.3+3*Math.sin(i*Math.PI/32);roofVertices.push(x,y,-12,x,y,2);if(i<32){const k=i*2;roofIndices.push(k,k+1,k+2,k+1,k+3,k+2);}}
    const roofGeometry=new THREE.BufferGeometry();roofGeometry.setAttribute('position',new THREE.Float32BufferAttribute(roofVertices,3));roofGeometry.setIndex(roofIndices);roofGeometry.computeVertexNormals();extras.push(roofGeometry);
    const roofMaterial=new THREE.MeshStandardMaterial({color:'#577383',metalness:.65,roughness:.18,side:THREE.DoubleSide});materials.push(roofMaterial);scene.add(new THREE.Mesh(roofGeometry,roofMaterial));
    for(let i=0;i<7;i++)box(0,.12+i*.07,3+i*.48,23,.16,.48,white);
    // The EcoRoute gateway glyph, integrated into the station façade.
    const left=box(-.65,6.5,2.1,.23,2,.23,orange);left.rotation.z=-.47;
    const right=box(.2,6.5,2.1,.23,2,.23,orange);right.rotation.z=.47;
    const treeGeo=new THREE.IcosahedronGeometry(1,1);extras.push(treeGeo);
    function tree(x:number,z:number,s=1){box(x,1.25*s,z,.2*s,2.5*s,.2*s,bark);for(let i=0;i<3;i++){const mesh=new THREE.Mesh(treeGeo,foliage);mesh.position.set(x+(i-1)*.65*s,(3+i*.2)*s,z+(i%2)*.5);mesh.scale.set(1.2*s,1.65*s,1.2*s);mesh.castShadow=true;scene.add(mesh);}box(x,.15,z,2,.3,2,ivory);}
    for(let x=-78;x<80;x+=8){if(Math.abs(x)>16)tree(x,5,1.2);tree(x,24,1.2);tree(x,-19,.8);}
    // Street furniture, crossings and cars give scale without adding geographic claims.
    for(const x of [-31,32])for(let i=0;i<7;i++)box(x-2.6+i*.85,.15,14,.45,.035,8,white);
    for(let x=-64;x<70;x+=16){box(x,.6,25,2.6,.2,.65,bark);box(x-1,.3,25,.12,.6,.5,dark);box(x+1,.3,25,.12,.6,.5,dark);}
    for(const x of [-55,-22,34,61]){box(x,.6,-24,3.3,.85,1.5,silver);box(x,.99,-24,1.7,.55,1.35,dark);box(x+1.68,.63,-24,.05,.15,1.1,warm);}
    for(let x=-80;x<85;x+=12){box(x,2.8,8,.1,5.6,.1,dark);box(x+.6,5.5,8,1.4,.13,.4,warm);}
    function tram(z:number){const g=new THREE.Group();scene.add(g);for(let i=0;i<3;i++){const x=i*4.8;box(x,1.25,0,4.5,2,1.7,white,g);box(x,1.6,.87,3.8,.85,.06,dark,g);box(x,1.6,-.87,3.8,.85,.06,dark,g);box(x-1.3,1.2,.92,.6,1.85,.07,orange,g);box(x,2.35,0,4,.15,1.6,silver,g);box(x,.32,0,3.4,.5,1.4,dark,g);}g.position.set(0,0,z);return g;}
    const trams=[tram(11.3),tram(16.9)];
    // Batch the static city by geometry/material: hundreds of boxes become a handful of draws.
    for(const geometry of [boxGeometry,treeGeo]){
      const groups=new Map<THREE.Material,THREE.Mesh[]>();
      for(const child of [...scene.children])if(child instanceof THREE.Mesh && child.geometry===geometry){const material=child.material as THREE.Material;const group=groups.get(material)||[];group.push(child);groups.set(material,group);}
      for(const [material,meshes] of groups){const instances=new THREE.InstancedMesh(geometry,material,meshes.length);meshes.forEach((mesh,index)=>{mesh.updateMatrix();instances.setMatrixAt(index,mesh.matrix);scene.remove(mesh);});instances.castShadow=true;instances.receiveShadow=true;instances.instanceMatrix.needsUpdate=true;scene.add(instances);}
    }
    const changed=()=>{dirty.current=true;};controls.addEventListener('change',changed);
    controls.update();
    const resize=()=>{const {width,height}=element.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();dirty.current=true;};
    const observer=new ResizeObserver(resize);observer.observe(element);resize();
    let frame=0,last=0,elapsed=0;const animate=(time:number)=>{frame=requestAnimationFrame(animate);if(time-last<32)return;const dt=Math.min((time-last)/1000,.1);last=time;
      if(document.hidden)return;if(motion.current){elapsed+=dt;dirty.current=true;}
      trams[0].position.x=((elapsed*3+25)%180)-90;trams[1].position.x=90-((elapsed*3+75)%180);
      controls.update();if(dirty.current){renderer.render(scene,camera);dirty.current=false;}
    };frame=requestAnimationFrame(animate);
    const loss=(event:Event)=>{event.preventDefault();setFailed(true);};renderer.domElement.addEventListener('webglcontextlost',loss);
    return()=>{cancelAnimationFrame(frame);observer.disconnect();controls.removeEventListener('change',changed);controls.dispose();skyGeometry.dispose();skyMaterial.dispose();boxGeometry.dispose();extras.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());windowTexture.dispose();env.dispose();room.dispose();pmrem.dispose();renderer.dispose();renderer.domElement.removeEventListener('webglcontextlost',loss);renderer.domElement.remove();api.current=undefined;};
  },[]);
  useEffect(()=>{const value=api.current;if(!value)return;const delta=value.camera.position.clone().sub(value.controls.target).normalize();value.camera.position.copy(value.controls.target).addScaledVector(delta,Math.max(48,Math.min(130,94-zoom*10)));},[zoom]);
  useEffect(()=>{const value=api.current;if(value){value.camera.position.set(46,19,78);value.controls.target.set(0,9,-12);}},[reset]);
  return <div ref={host} className="city-canvas">{failed&&<div className="webgl-fallback"><h2>Your routes, without the 3D view.</h2><p>WebGL is unavailable on this device. Use Route view to explore the actual geometry.</p></div>}</div>;
}
