import {Leaf, Wind} from 'lucide-react';
import {number, weightedConcentration, type Route} from './data';
import './journey-metrics.css';

export default function JourneyMetrics({route,routeIndex,live,sharedForecast}:{route?:Route;routeIndex:number;live:boolean;sharedForecast:boolean}) {
  const concentration=weightedConcentration(route);
  const concentrationText=number(concentration);
  const readingSize=concentrationText.length>=7?20:concentrationText.length>=6?23:concentrationText.length>=5?28:34;
  const coverage=route&&Number.isFinite(route.pm25_coverage_fraction)?Math.round(Math.min(1,Math.max(0,route.pm25_coverage_fraction))*100):null;
  return <>
    <section className="air-instrument selected-route-air" aria-label="Selected route air quality">
      <div className="instrument-label"><Wind size={18}/> PM2.5</div>
      <div className="selected-route-context" aria-live="polite" aria-atomic="true">
        <strong>{route?`Route ${routeIndex+1} selected`:'Choose a route'}</strong>
        {route&&<span>{number(route.duration_s/60)} min · {number(route.distance_m/1000)} km</span>}
      </div>
      <div className="air-ring"><svg viewBox="0 0 180 180" aria-hidden="true"><circle cx="90" cy="90" r="82" fill="none" stroke="#919d9f" strokeWidth="2" strokeDasharray="1 5"/><circle cx="90" cy="90" r="75" fill="none" stroke="#bbc3c4" strokeWidth="1" strokeDasharray="1 4"/><path d="M90 8 A82 82 0 0 1 172 90" fill="none" stroke="#e95e23" strokeWidth="3" strokeDasharray="1 5"/></svg><div><strong style={{fontSize:`${readingSize}px`}} data-testid="selected-pm25">{concentrationText}</strong><span>µg/m³</span></div></div>
      <p>Route-weighted concentration</p>
      <span className="small-badge">{live?'Returned route data':'Recorded forecast'}</span>
      {route&&sharedForecast&&concentration!==null&&<p className="shared-forecast-note">Shared grid: PM2.5 can match.</p>}
    </section>
    <section className="coverage-instrument selected-route-exposure" aria-label="Selected route exposure">
      <div className="instrument-label">Your route exposure</div>
      <span className="round-orange"><Leaf size={22}/></span>
      <strong data-testid="selected-exposure">{number(route?.estimated_pm25_exposure_ug_h_m3,2)}</strong>
      <span className="exposure-unit">µg·h/m³</span>
      <p>Estimated exposure</p>
      <div className="selected-coverage-row"><span>Data coverage</span><strong data-testid="selected-coverage">{coverage??'—'}{coverage!==null?'%':''}</strong></div>
      <div className="coverage-track" aria-hidden="true"><i style={{width:`${coverage||0}%`}}/></div>
      <span className="rail-small">{route?.estimated_pm25_exposure_ug_h_m3==null?'Complete pollution coverage is needed.':'PM2.5 × travel time.'}</span>
    </section>
  </>;
}
