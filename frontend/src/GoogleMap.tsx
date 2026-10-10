/// <reference types="google.maps" />
import {useEffect,useRef,useState} from 'react';
import type {Route} from './data';
export const mapsKey=import.meta.env.VITE_GOOGLE_MAPS_API_KEY||'';
let loading:Promise<void>|undefined;
function loadMaps(){
 if(window.google?.maps)return Promise.resolve();
 return loading ||= new Promise<void>((resolve,reject)=>{
  const script=document.createElement('script');const timer=setTimeout(()=>reject(new Error('Google Maps timed out. Check your connection and key restrictions.')),15000);
  Object.assign(window,{ecoGoogleReady:()=>{clearTimeout(timer);resolve();},gm_authFailure:()=>{window.dispatchEvent(new Event('google-map-auth-error'));clearTimeout(timer);reject(new Error('Google Maps authorization failed. Check billing and website restrictions.'));}});
  script.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(mapsKey)}&loading=async&callback=ecoGoogleReady&v=weekly`;
  script.async=true;script.onerror=()=>{clearTimeout(timer);reject(new Error('Google Maps could not load.'));};document.head.append(script);
 });
}
export default function GoogleMap({routes,selected,onSelect}:{routes:Route[];selected:string;onSelect:(id:string)=>void}){
 const host=useRef<HTMLDivElement>(null),map=useRef<google.maps.Map|null>(null);
 const [ready,setReady]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let active=true;const authError=()=>{setReady(false);setError('Google Maps authorization failed. Check billing and website restrictions.');};window.addEventListener('google-map-auth-error',authError);if(!mapsKey){setError('Add VITE_GOOGLE_MAPS_API_KEY to frontend/.env.local to enable the Journeys map.');return()=>window.removeEventListener('google-map-auth-error',authError);}
  loadMaps().then(()=>{if(!active||!host.current)return;map.current=new google.maps.Map(host.current,{center:{lat:28.6139,lng:77.209},zoom:12,mapTypeControl:false,streetViewControl:false,fullscreenControl:true,gestureHandling:'cooperative'});setReady(true);}).catch(e=>{if(active)setError(e.message);});
  return()=>{active=false;map.current=null;window.removeEventListener('google-map-auth-error',authError);};
 },[]);
 useEffect(()=>{if(!ready||!map.current)return;const bounds=new google.maps.LatLngBounds();
  const overlays=routes.map(route=>{const path=route.geometry.coordinates.map(([lng,lat])=>({lat,lng}));path.forEach(p=>bounds.extend(p));
   const line=new google.maps.Polyline({map:map.current,path,strokeColor:route.route_id===selected?'#ef682b':'#586f84',strokeWeight:route.route_id===selected?7:4,zIndex:route.route_id===selected?2:1});line.addListener('click',()=>onSelect(route.route_id));return line;});
  const active=routes.find(r=>r.route_id===selected)||routes[0];
  const endpoints=active?[active.geometry.coordinates[0],active.geometry.coordinates.at(-1)!].map(([lng,lat],i)=>new google.maps.Circle({map:map.current,center:{lat,lng},radius:35,fillColor:i?'#ef682b':'#25292b',fillOpacity:1,strokeColor:'#ffffff',strokeWeight:3,zIndex:3})):[];
  if(routes.length)map.current.fitBounds(bounds,50);
  return()=>[...overlays,...endpoints].forEach(line=>{google.maps.event.clearInstanceListeners(line);line.setMap(null);});
 },[ready,routes,selected,onSelect]);
 return <div className="google-map-area"><div ref={host} className="google-map-host" aria-label="Journey map"/>{!ready&&<div className="map-setup" role="status">{error||'Loading Google Maps...'}</div>}</div>;
}
