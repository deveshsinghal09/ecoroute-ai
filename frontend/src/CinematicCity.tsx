import { trainPose, stripPose, STRIPS, SPRITE_WIDTH } from './trainMotion';
import { useEffect, useRef, useState } from 'react';

/** One layered city: fixed architectural artwork and independently moving train sprites. */
export default function CinematicCity({moving,zoom,reset}:{moving:boolean;zoom:number;reset:number}) {
  const host=useRef<HTMLDivElement>(null);
  const trains=useRef<Array<SVGGElement|null>>([]);
  const slices=useRef<Array<SVGGElement|null>>([]);
  const elapsed=useRef(0);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{elapsed.current=0;host.current?.style.setProperty('--look-x','0px');host.current?.style.setProperty('--look-y','0px');},[reset]);
  useEffect(()=>{
    let frame=0,last=0;
    const draw=(time:number)=>{
      if(last&&moving&&!document.hidden)elapsed.current+=Math.min((time-last)/1000,.08);
      last=time;
      for(let i=0;i<2;i++){
        const {x}=trainPose(elapsed.current,i);
        trains.current[i]?.setAttribute('transform','translate(0 0)');
        trains.current[i]?.setAttribute('data-position',x.toFixed(3));
        for(let layer=0;layer<2;layer++)for(let strip=0;strip<STRIPS;strip++){
          const p=stripPose(elapsed.current,i,strip,layer===0);
          slices.current[i*STRIPS*2+layer*STRIPS+strip]?.setAttribute('transform',`matrix(${p.a} ${p.b} 0 ${p.d} ${p.e} ${p.f})`);
        }
      }
      if(moving)frame=requestAnimationFrame(draw);
    };
    draw(performance.now());return()=>cancelAnimationFrame(frame);
  },[moving,reset]);
  return <div ref={host} className="cinematic-city" onPointerMove={event=>{
    if(!moving||event.pointerType==='touch')return;
    const bounds=event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty('--look-x',`${(event.clientX-bounds.left-bounds.width/2)*-.006}px`);
    event.currentTarget.style.setProperty('--look-y',`${(event.clientY-bounds.top-bounds.height/2)*-.006}px`);
  }} onPointerLeave={()=>{host.current?.style.setProperty('--look-x','0px');host.current?.style.setProperty('--look-y','0px');}}>
    <div className="cinematic-zoom" style={{transform:`scale(${1.025+Math.max(0,zoom)*.055})`}}>
      <svg className="cinematic-art" viewBox="0 0 1672 941" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustrative city with moving orange and white trains, a glass station and reflective streets">
        <defs>{Array.from({length:STRIPS},(_,strip)=><clipPath id={`tram-strip-${strip}`} key={strip}><rect x={strip*SPRITE_WIDTH/STRIPS} y="0" width={SPRITE_WIDTH/STRIPS+.12} height="138.18"/></clipPath>)}</defs>
        <image className="city-backdrop" href="/assets/ecoroute-city-clear.png" width="1672" height="941" onError={()=>setFailed(true)}/>
        {[0,1].map(i=><g key={i} ref={element=>{trains.current[i]=element;}} className="animated-train" data-train={i}>
          {[0,1].map(layer=><g key={layer} opacity={layer===0?.14:1}>
            {Array.from({length:STRIPS},(_,strip)=><g key={strip} ref={element=>{slices.current[i*STRIPS*2+layer*STRIPS+strip]=element;}}>
              <image className={layer===1?'train-sprite':'train-reflection'} href="/assets/ecoroute-tram.png" x="0" y="0" width="380" height="138.18" clipPath={`url(#tram-strip-${strip})`} onError={()=>setFailed(true)}/>
            </g>)}
          </g>)}
        </g>)}
      </svg>
    </div>
    {failed&&<p className="art-unavailable">City artwork could not load. Route planning remains available.</p>}
  </div>;
}
