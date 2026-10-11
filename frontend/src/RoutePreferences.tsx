import {useState} from 'react';
import {request} from './api';
import './route-preferences.css';

export const defaultPreferences={exposure_weight:.5,weather_weight:0,terrain_weight:0,avoid_tolls:false,avoid_highways:false,avoid_ferries:false,avoid_steps:false};
export type Preferences=typeof defaultPreferences;
export type ForecastChoice={model_version:string;station_ids:string[]}|null;
type Model={model_version:string;verified:boolean;supported_stations:string[];horizon_hours:number};
export function compatiblePreferences(value:Preferences,mode:string):Preferences {
  return {...value,avoid_tolls:mode==='driving'&&value.avoid_tolls,avoid_highways:mode==='driving'&&value.avoid_highways,
    avoid_ferries:mode==='driving'&&value.avoid_ferries,avoid_steps:mode==='cycling'&&value.avoid_steps,terrain_weight:mode==='cycling'?value.terrain_weight:0};
}

export default function RoutePreferences({mode,value,onChange,authenticated,forecast,onForecast}:{mode:string;value:Preferences;onChange:(v:Preferences)=>void;authenticated:boolean;forecast:ForecastChoice;onForecast:(v:ForecastChoice)=>void}) {
  const [models,setModels]=useState<Model[]>([]),[status,setStatus]=useState(''),[busy,setBusy]=useState(false);
  async function check(){
    setBusy(true);setStatus('Checking verified station models…');
    try {
      const result=await request<{models:Model[]}>('/ml/models');
      const usable=result.models.filter(m=>m.verified&&m.supported_stations.length>0&&m.horizon_hours===1);
      setModels(usable);onForecast(null);
      setStatus(usable.length?'Verified station forecasts available. They apply near their monitoring stations only.':'No model is approved for navigation. Routes continue to use available observed/provider forecast data.');
    }catch{setModels([]);onForecast(null);setStatus('Station inference is unavailable. Configure the inference worker and an approved local monitoring model; experimental models cannot be used.');}
    finally{setBusy(false);}
  }
  const time=1-value.exposure_weight-value.weather_weight-(mode==='cycling'?value.terrain_weight:0);
  return <details className="route-preferences"><summary>Route factors & forecasts</summary><div className="route-preferences-body">
    <p>Driving time already includes Google traffic. Exposure uses concentration × travel time.</p>
    <label>Pollution priority <output>{Math.round(value.exposure_weight*100)}%</output><input aria-label="Pollution priority" type="range" min="0" max="60" step="10" value={value.exposure_weight*100} onChange={e=>onChange({...value,exposure_weight:Number(e.target.value)/100})}/></label>
    <label>Weather preference <output>{Math.round(value.weather_weight*100)}%</output><input aria-label="Weather preference" type="range" min="0" max="20" step="10" value={value.weather_weight*100} onChange={e=>onChange({...value,weather_weight:Number(e.target.value)/100})}/></label>
    {mode==='cycling'&&<label>Lower climbing preference <output>{Math.round(value.terrain_weight*100)}%</output><input aria-label="Climbing preference" type="range" min="0" max="20" step="10" value={value.terrain_weight*100} onChange={e=>onChange({...value,terrain_weight:Number(e.target.value)/100})}/></label>}
    <p>Travel time: {Math.round(time*100)}%. Weather and elevation are estimates; missing weighted inputs prevent a balanced recommendation.</p>
    {mode==='driving'&&(['avoid_tolls','avoid_highways','avoid_ferries'] as const).map(key=><label className="route-preference-check" key={key}><input type="checkbox" checked={value[key]} onChange={e=>onChange({...value,[key]:e.target.checked})}/>{({avoid_tolls:'Prefer avoiding tolls',avoid_highways:'Prefer avoiding highways',avoid_ferries:'Prefer avoiding ferries'})[key]}</label>)}
    {mode==='cycling'&&<label className="route-preference-check"><input type="checkbox" checked={value.avoid_steps} onChange={e=>onChange({...value,avoid_steps:e.target.checked})}/>Request routes avoiding steps</label>}
    <button className="secondary-button" type="button" disabled={!authenticated||busy} onClick={()=>void check()}>{busy?'Checking models…':'Check station forecast availability'}</button>
    {!authenticated&&<p>Sign in to use protected station predictions.</p>}
    {status&&<p role="status">{status}</p>}
    {models.length>0&&<label>Pollution source<select aria-label="Pollution source" value={forecast?.model_version||''} onChange={e=>{const model=models.find(m=>m.model_version===e.target.value);onForecast(model?{model_version:model.model_version,station_ids:model.supported_stations.slice(0,20)}:null);}}><option value="">Observed / provider forecasts</option>{models.map(m=><option key={m.model_version} value={m.model_version}>Verified station model {m.model_version.slice(0,8)}</option>)}</select></label>}
  </div></details>;
}
