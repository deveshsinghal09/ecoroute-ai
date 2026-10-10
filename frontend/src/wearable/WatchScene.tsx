import {useEffect,useMemo,useRef} from 'react';
import {Canvas,useFrame,useThree} from '@react-three/fiber';
import {CanvasTexture,ShapeGeometry,LinearFilter,ExtrudeGeometry,Group,Path,Shape,SRGBColorSpace,MathUtils,MeshBasicMaterial} from 'three';
import {paintScreen} from './watchScreen';
import type {WatchData,WatchPage,WatchSettings} from './watchData';

function outline(w:number,h:number,r:number){
 const s=new Shape(),x=-w/2,y=-h/2;
 s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r);s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h);s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r);s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);return s;
}
function geometry(w:number,h:number,r:number,depth:number,holes=false){
 const shape=outline(w,h,r);
 if(holes)for(let i=0;i<5;i++){const hole=new Path();hole.absellipse(0,-h/2+.26+i*.29,.13,.055,0,Math.PI*2,true);shape.holes.push(hole);}
 return new ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelSegments:3,steps:1,bevelSize:.045,bevelThickness:.04,curveSegments:12});
}
type Props={data?:WatchData;page:WatchPage;settings:WatchSettings;animate:boolean;tilt:{x:number;y:number};onNext:()=>void;onHome:()=>void;onFailure:()=>void;onReady:()=>void};

function Product({data,page,settings,animate,tilt,onNext,onHome,onFailure,onReady}:Props){
 const group=useRef<Group>(null);const display=useRef<MeshBasicMaterial>(null);const changed=useRef(0);const start=useRef<number|null>(null);const pulseFrame=useRef(0);const {invalidate,gl}=useThree();
 const pieces=useMemo(()=>({case:geometry(2.45,2.86,.49,.30),bezel:geometry(2.40,2.81,.47,.045),glass:geometry(2.27,2.65,.43,.045),screen:new ShapeGeometry(outline(2.12,2.49,.35),24),upper:geometry(1.48,1.76,.20,.12),lower:geometry(1.48,1.93,.28,.12,true),keeper:geometry(1.62,.22,.05,.08)}),[]);
 const texture=useMemo(()=>{const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=1200;const texture=new CanvasTexture(canvas);texture.colorSpace=SRGBColorSpace;texture.anisotropy=8;texture.generateMipmaps=false;texture.minFilter=LinearFilter;texture.magFilter=LinearFilter;return texture;},[]);
 // ShapeGeometry UVs are world coordinates; normalize them for the screen texture.
 useMemo(()=>{const uv=pieces.screen.getAttribute('uv'),pos=pieces.screen.getAttribute('position');for(let i=0;i<uv.count;i++){uv.setXY(i,(pos.getX(i)+1.06)/2.12,(pos.getY(i)+1.245)/2.49);}uv.needsUpdate=true;},[pieces]);
 useEffect(()=>{changed.current=performance.now();const paint=()=>{paintScreen(texture.image as HTMLCanvasElement,page,data,settings,new Date());texture.needsUpdate=true;invalidate();};paint();const timer=setInterval(paint,15000);return()=>clearInterval(timer);},[texture,page,data,settings,invalidate]);
 useEffect(()=>{const lost=(e:Event)=>{e.preventDefault();onFailure();};gl.domElement.addEventListener('webglcontextlost',lost);onReady();return()=>gl.domElement.removeEventListener('webglcontextlost',lost);},[gl,onFailure,onReady]);
 useEffect(()=>()=>{Object.values(pieces).forEach(g=>g.dispose());texture.dispose();},[pieces,texture]);
 useFrame(({clock},delta)=>{
  if(display.current)display.current.opacity=animate?Math.min(1,(performance.now()-changed.current)/250):1;
  if(!group.current)return;start.current??=clock.elapsedTime;const t=clock.elapsedTime-start.current;
  if(animate&&page==='Heart'&&clock.elapsedTime-pulseFrame.current>.12){pulseFrame.current=clock.elapsedTime;paintScreen(texture.image as HTMLCanvasElement,page,data,settings,new Date());texture.needsUpdate=true;}
  const g=group.current;const ease=animate?1-Math.exp(-delta*5):1;
  g.rotation.x=MathUtils.lerp(g.rotation.x,tilt.y*.08,ease);
  g.rotation.y=MathUtils.lerp(g.rotation.y,tilt.x*.14-.035,ease);
  g.rotation.z=MathUtils.lerp(g.rotation.z,-.02,ease);
  g.position.y=animate?Math.sin(t*.8)*.055:0;
  g.scale.setScalar(animate?Math.min(1,.93+t*.15):1);
 });
 return <group ref={group}>
  <mesh geometry={pieces.upper} position={[0,2.90,-.045]}><meshStandardMaterial color="#172127" roughness={.8}/></mesh>
  <mesh geometry={pieces.lower} position={[0,-2.97,-.045]}><meshStandardMaterial color="#172127" roughness={.8}/></mesh>
  {[-1,1].flatMap(sign=>Array.from({length:8},(_,i)=><mesh key={`${sign}-${i}`} position={[0,sign*(2.22+i*.17),.105]}><boxGeometry args={[1.3,.017,.02]}/><meshStandardMaterial color="#33505a" roughness={.85}/></mesh>))}
  <mesh geometry={pieces.keeper} position={[0,3.39,.105]}><meshStandardMaterial color="#0e2028" roughness={.55}/></mesh>
  <group scale={1.45}>
  <mesh geometry={pieces.case} position={[0,0,-.07]}><meshStandardMaterial color="#313d44" metalness={.86} roughness={.29}/></mesh>
  <mesh geometry={pieces.bezel} position={[0,0,.265]}><meshStandardMaterial color="#a3b9c4" metalness={.9} roughness={.23}/></mesh>
  <mesh geometry={pieces.glass} position={[0,0,.326]}><meshPhysicalMaterial color="#02080f" metalness={.15} roughness={.15} clearcoat={1} clearcoatRoughness={.07}/></mesh>
  <mesh name="interactive-watch-display" geometry={pieces.screen} position={[0,0,.420]} onClick={e=>{e.stopPropagation();if(e.delta<5)onNext();}}><meshBasicMaterial ref={display} transparent map={texture} toneMapped={false} color={`hsl(0, 0%, ${settings.brightness}%)`}/></mesh>
  <mesh position={[-.96,.14,.446]}><boxGeometry args={[.012,1.52,.008]}/><meshBasicMaterial color="#bcf4ff" transparent opacity={.23}/></mesh>
  <group position={[1.32,.30,.12]} rotation={[0,0,Math.PI/2]} onClick={e=>{e.stopPropagation();if(e.delta<5)onHome();}}>
   <mesh><boxGeometry args={[.48,.45,.5]}/><meshBasicMaterial transparent opacity={0} depthWrite={false}/></mesh>
   <mesh><cylinderGeometry args={[.18,.18,.19,32]}/><meshStandardMaterial color="#6a8797" metalness={.85} roughness={.24}/></mesh>
   <mesh position={[0,-.105,0]}><cylinderGeometry args={[.11,.11,.025,24]}/><meshStandardMaterial color={settings.accent} emissive={settings.accent} emissiveIntensity={.3}/></mesh>
   {Array.from({length:18},(_,i)=><mesh key={i} position={[Math.cos(i*Math.PI/9)*.179,0,Math.sin(i*Math.PI/9)*.179]} rotation={[0,-i*Math.PI/9,0]}><boxGeometry args={[.017,.17,.02]}/><meshStandardMaterial color="#20333d" metalness={.8}/></mesh>)}
  </group>
  <mesh position={[1.27,-.5,.1]}><boxGeometry args={[.09,.42,.13]}/><meshStandardMaterial color="#354d59" metalness={.8} roughness={.3}/></mesh>
  <mesh position={[0,-1.32,.388]}><boxGeometry args={[.26,.026,.017]}/><meshBasicMaterial color={settings.accent}/></mesh>
 </group></group>;
}

export default function WatchScene(props:Props){
 return <Canvas orthographic camera={{position:[0,0,12],zoom:60,near:.1,far:40}} dpr={2} frameloop={props.animate?'always':'demand'} gl={{antialias:true,alpha:true,powerPreference:'low-power'}} style={{touchAction:'pan-y'}}>
  <ambientLight intensity={1.5}/><directionalLight position={[-4,5,8]} intensity={4} color="#d4faff"/><directionalLight position={[4,-2,5]} intensity={2.5} color="#779eff"/><pointLight position={[0,4,3]} intensity={8} color="#ffffff"/>
  <Fit/><Product {...props}/>
 </Canvas>;
}
function Fit(){const {camera,size,invalidate}=useThree();useEffect(()=>{if('zoom' in camera){camera.zoom=Math.min(size.height/8.6,size.width/4.9);camera.updateProjectionMatrix();invalidate();}},[camera,size,invalidate]);return null;}
