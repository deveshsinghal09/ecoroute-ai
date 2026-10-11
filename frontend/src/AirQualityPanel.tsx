import {useEffect,useRef,useState} from 'react';
import {ArrowUpRight,Check,Info,LoaderCircle} from 'lucide-react';
import {request} from './api';
import {airQuality,datasetSummary} from './airQuality';
import {number,type Route} from './data';
import './air-quality.css';

function revealCheck(element:HTMLElement|null){element?.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}

export default function AirQualityPanel({route,live,authenticated,onPlan}:{route?:Route;live:boolean;authenticated:boolean;onPlan:()=>void}) {
  const [checked,setChecked]=useState(false);
  const checkRef=useRef<HTMLDivElement>(null);
  const [dataset,setDataset]=useState('');const [error,setError]=useState('');const [loading,setLoading]=useState(false);
  const air=airQuality(route,live);
  useEffect(()=>{if(checked)revealCheck(checkRef.current);},[checked]);
  async function checkDatasets(){
    setLoading(true);setError('');setDataset('');
    try{setDataset(datasetSummary(await request('/data/quality')));}
    catch{setError('We could not check collected datasets. Try again; if your session has ended, sign in again. Your route data check above is still available.');}
    finally{setLoading(false);}
  }
  return <section className="air-quality-content" aria-label="Air along your journey">
    <h3>{air.dataTitle}</h3>
    {air.concentration!==null&&<div className="air-quality-reading"><strong>{number(air.concentration)}</strong><span>µg/m³ <small>PM2.5 estimate</small></span></div>}
    <p className="panel-description">{air.description}</p>
    {!route?<button className="primary-button" onClick={onPlan}>Choose a route <ArrowUpRight size={17}/></button>:<>
      <dl className="air-quality-facts"><div><dt>Data available for</dt><dd>{air.coverageText}</dd></div><div><dt>Based on</dt><dd>{air.type}</dd></div></dl>
      <p className="note">{!live?'Saved results, not today’s air. ':''}Air data describes an area, not every street. This particle reading is different from an AQI score.</p>
      {air.outdated&&<p className="note">This forecast is over 24 hours old. Compare again to refresh it.</p>}
      <button className="secondary-button" onClick={()=>{if(checked)revealCheck(checkRef.current);else setChecked(true);}}>Check route data <ArrowUpRight size={15}/></button>
      {checked&&<div ref={checkRef} className="air-quality-check" role="status"><h4>Route data check</h4><p>Checked the results already returned for this route. This does not fetch new readings.</p><ul>{air.checks.map(check=><li key={check.title}>{check.ok?<Check size={16} aria-hidden="true"/>:<Info size={16} aria-hidden="true"/>}<span><strong>{check.title}</strong>{check.detail}</span></li>)}</ul></div>}
      <details className="air-quality-details"><summary>About this estimate</summary>
        <dl className="air-quality-facts"><div><dt>Source</dt><dd>{air.names.join(', ')||'Not supplied'}</dd></div><div><dt>Area size</dt><dd>{air.resolution.length?air.resolution.map(km=>`About ${number(km,0)} km`).join(', '):'Not supplied'}</dd></div><div><dt>Forecast downloaded</dt><dd>{air.oldest===null?'Not supplied':new Date(air.oldest).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'})}</dd></div><div><dt>Confidence</dt><dd>{route.confidence==='low'?'Limited detail':route.confidence==='medium'?'Moderate':route.confidence==='high'?'High':route.confidence==='limited'?'Limited detail':'Not available'}</dd></div></dl>
        {authenticated&&live?<><button className="secondary-button" disabled={loading} onClick={()=>void checkDatasets()}>{loading?<LoaderCircle size={15} className="spin"/>:null}{loading?'Checking collected datasets…':'Check collected datasets'}</button>{dataset&&<p className="note" role="status">{dataset}</p>}{error&&<p className="air-quality-error" role="alert">{error}</p>}</>:<p className="note">{live?'Checking collected datasets separately requires sign-in. The route data check above works without it.':'The route data check uses this saved comparison.'}</p>}
      </details>
    </>}
  </section>;
}
