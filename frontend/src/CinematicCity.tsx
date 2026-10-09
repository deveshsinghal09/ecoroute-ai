import { trainPose } from './trainMotion';
import { useEffect, useRef, useState } from 'react';

/** One layered city: fixed architectural artwork and independently moving train sprites. */
export default function CinematicCity({moving,zoom,reset}:{moving:boolean;zoom:number;reset:number}) {
  const host=useRef<HTMLDivElement>(null);
  const trains=useRef<Array<SVGGElement|null>>([]);
  const elapsed=useRef(0);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{elapsed.current=0;host.current?.style.setProperty('--look-x','0px');host.current?.style.setProperty('--look-y','0px');},[reset]);
  useEffect(()=>{
    let frame=0,last=0;
    const draw=(time:number)=>{
      if(last&&moving&&!document.hidden)elapsed.current+=Math.min((time-last)/1000,.08);
      last=time;
      for(let i=0;i<2;i++){
        const {x,y,angle,scale}=trainPose(elapsed.current,i);
        trains.current[i]?.setAttribute('transform',`translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${angle.toFixed(2)}) scale(${scale.toFixed(3)})`);
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
        <defs><linearGradient id="reflection-fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="white" stopOpacity=".4"/><stop offset="1" stopColor="white" stopOpacity="0"/></linearGradient><mask id="reflection-mask"><rect x="-240" y="0" width="480" height="135" fill="url(#reflection-fade)"/></mask></defs>
        <image className="city-backdrop" href="/assets/ecoroute-city-clear.png" width="1672" height="941" onError={()=>setFailed(true)}/>
        {[0,1].map(i=><g key={i} ref={element=>{trains.current[i]=element;}} className="animated-train" data-train={i}>
          <ellipse cx="0" cy="-2" rx="173" ry="9" fill="#14232c" opacity=".18"/>
          <g mask="url(#reflection-mask)"><image href="/assets/ecoroute-tram.png" x="-190" y="-134" width="380" height="134" transform="scale(1 -1)" opacity=".65"/></g>
          <image className="train-sprite" href="/assets/ecoroute-tram.png" x="-190" y="-134" width="380" height="134" onError={()=>setFailed(true)}/>
        </g>)}
      </svg>
    </div>
    {failed&&<p className="art-unavailable">City artwork could not load. Route planning remains available.</p>}
  </div>;
}
