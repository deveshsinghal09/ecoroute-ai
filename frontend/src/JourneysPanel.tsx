import {ArrowUpRight,ArrowRight,Navigation} from 'lucide-react';
import {number,type Comparison,type Route} from './data';
import {airQuality} from './airQuality';
import RouteOptions from './RouteOptions';
import './journeys.css';

export default function JourneysPanel({comparison,route,labels,live,settingsChanged,onSelect,onPlan,onAir,onInsights}:{comparison:Comparison|null;route?:Route;labels:{origin:string;destination:string};live:boolean;settingsChanged:boolean;onSelect:(id:string)=>void;onPlan:()=>void;onAir:()=>void;onInsights:()=>void}) {
  if(!route||!comparison)return <section className="journeys-content" aria-label="Current journey"><Navigation size={28} aria-hidden="true"/><h3>No journey to review yet.</h3><p className="panel-description">Plan a route in City overview. Your selected route and alternatives will appear here.</p><button className="primary-button" onClick={onPlan}>Plan a journey <ArrowUpRight size={17}/></button></section>;
  const index=comparison.routes.findIndex(r=>r.route_id===route.route_id);
  const air=airQuality(route,live);
  const departed=Date.parse(route.departure_at);
  const arrival=departed+route.duration_s*1000;
  const dateText=(value:number)=>Number.isFinite(value)?new Date(value).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'}):'Not supplied';
  return <section className="journeys-content" aria-label="Current journey">
    <dl className="journey-endpoints"><div><dt>From</dt><dd>{labels.origin}</dd></div><div><dt>To</dt><dd>{labels.destination}</dd></div></dl>
    <p className="journey-selection"><strong>Selected · Route {index+1}</strong><span>{live?'Current comparison':'Saved comparison'}</span></p>
    <dl className="journey-summary"><div><dt>Travel time</dt><dd>{number(route.duration_s/60)} <small>min</small></dd></div><div><dt>Distance</dt><dd>{number(route.distance_m/1000)} <small>km</small></dd></div></dl>
    <p className="journey-air-summary">{air.concentration===null?'Air estimate unavailable for this journey.':<>Average PM2.5 estimate <strong>{number(air.concentration)} µg/m³</strong></>}</p>
    <div className="journey-actions"><button className="secondary-button" onClick={onAir}>View air estimate <ArrowUpRight size={14}/></button><button className="secondary-button" onClick={onInsights}>Explain this journey <ArrowUpRight size={14}/></button></div>
    <div className="section-divider"><span>SWITCH ROUTE</span><small>{comparison.routes.length} {comparison.routes.length===1?'option':'options'}</small></div>
    <RouteOptions comparison={comparison} selected={route.route_id} onSelect={onSelect}/>
    <details className="journey-timing"><summary>Journey timing</summary><dl><div><dt>Departure</dt><dd>{dateText(departed)}</dd></div><div><dt>Estimated arrival</dt><dd>{dateText(arrival)}</dd></div></dl><p className="note">Times use your device’s time zone.{!live?' This saved comparison does not show current conditions.':''}</p></details>
    {settingsChanged&&<p className="note" role="status">Planner settings have changed. Edit your journey and compare again to update these results.</p>}
    <button className="journey-edit" onClick={onPlan}>Edit journey in City overview <ArrowRight size={15}/></button>
    {live&&comparison.persistence==='request_only'&&<p className="note">This comparison is not saved to your account.</p>}
  </section>;
}
