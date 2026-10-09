import { useEffect, useRef, useState } from 'react';

/** Reference-matched architectural artwork, explicitly separate from the real-time orbit mode. */
export default function CinematicCity({moving,zoom,reset}:{moving:boolean;zoom:number;reset:number}) {
  const host=useRef<HTMLDivElement>(null);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{host.current?.style.setProperty('--look-x','0px');host.current?.style.setProperty('--look-y','0px');},[reset,moving]);
  return <div ref={host} className={`cinematic-city ${moving?'is-moving':''}`} onPointerMove={event=>{
    if(!moving||event.pointerType==='touch')return;
    const bounds=event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty('--look-x',`${(event.clientX-bounds.left-bounds.width/2)*-.009}px`);
    event.currentTarget.style.setProperty('--look-y',`${(event.clientY-bounds.top-bounds.height/2)*-.009}px`);
  }} onPointerLeave={()=>{host.current?.style.setProperty('--look-x','0px');host.current?.style.setProperty('--look-y','0px');}}>
    <div className="cinematic-zoom" style={{transform:`scale(${1.025+Math.max(0,zoom)*.055})`}}><img className="cinematic-art" src="/assets/ecoroute-cinematic-city.png" alt="Illustrative architectural render of a glass transit station, orange-accented trams and reflective city streets under a cloudy sky." fetchPriority="high" onError={()=>setFailed(true)}/></div>
    {failed&&<p className="art-unavailable">City artwork could not load. Route planning remains available.</p>}
  </div>;
}
