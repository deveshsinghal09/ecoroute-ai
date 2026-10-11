import {ArrowUpRight,Check} from 'lucide-react';
import {number,type Comparison} from './data';
import {routeColor} from './routeStyle';

export default function RouteOptions({comparison,selected,onSelect}:{comparison:Comparison|null;selected:string;onSelect:(id:string)=>void}) {
  return <div className="route-options">{comparison?.routes.map((route,i)=><button key={route.route_id} className={`route-option ${selected===route.route_id?'chosen':''}`} aria-pressed={selected===route.route_id} onClick={()=>onSelect(route.route_id)}>
    {['google_routes','openrouteservice'].some(provider=>provider===route.routing_source.provider)&&<span className="google-attribution">{route.routing_source.provider==='google_routes'?'Google Maps':'openrouteservice / © OpenStreetMap contributors'}</span>}
    <span className="route-option-top"><span><span className={`route-dot route-${i}`} style={{background:routeColor(i)}}/>{route.route_id===comparison.recommended_route_ids.fastest?'Fastest route':'Alternative route'}</span>{selected===route.route_id?<Check size={16}/>:<ArrowUpRight size={15}/>}</span>
    <span className="route-figures"><strong>{number(route.duration_s/60)}<small> min</small></strong><span>{number(route.distance_m/1000)} km</span></span>
    <span className="route-exposure">{route.estimated_pm25_exposure_ug_h_m3===null?'Exposure unavailable':`${number(route.estimated_pm25_exposure_ug_h_m3,2)} µg·h/m³`} {route.estimated_pm25_exposure_ug_h_m3!==null&&<small>estimated exposure</small>}</span>
    {route.within_detour_limit===false&&<span className="route-detour-warning">Outside detour limit · {number(route.detour_percent,0)}% extra time</span>}
  </button>)}</div>;
}
