/* THESIS: Read actual phone records with explicit consent and visible provenance.
OWN-WORLD: Inherit the blue wearable panel, warm porcelain/orange controls and Manrope type.
STORY: Pair locally or sign in, allow a read, choose a day, and inspect available measurements.
FIRST VIEWPORT: Connection controls, date/refresh row and a compact eight-metric definition list.
FORM: Extend the existing wearable sidebar; retain the complete watch and every existing section. */
import {useCallback,useEffect,useRef,useState} from 'react';
import {RefreshCw,ShieldCheck,Unplug} from 'lucide-react';
import {requestHealthConnect} from '../api';
import {localDateKey,metricLabels,metricNote,metricText,watchDataFromHealthConnect,type HealthMetricKey,type HealthSummary} from './healthConnectData';
import type {WatchData} from './watchData';
import './health-connect.css';

export default function HealthConnectPanel({authenticated,onReadings}:{authenticated:boolean;onReadings:(data:WatchData|undefined)=>void}){
 const [keyInput,setKeyInput]=useState(''),[consent,setConsent]=useState(false),[connected,setConnected]=useState(false);
 const [summary,setSummary]=useState<HealthSummary>(),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [day,setDay]=useState(localDateKey()),[interval,setIntervalSeconds]=useState(0),[lastUpdate,setLastUpdate]=useState<string>();
 const zone=Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';
 const key=useRef(''),generation=useRef(0),pending=useRef<AbortController|null>(null),inFlight=useRef(false);
 const today=localDateKey(),oldest=new Date();oldest.setDate(oldest.getDate()-6);
 const clear=useCallback(()=>{generation.current++;pending.current?.abort();pending.current=null;key.current='';inFlight.current=false;
  setKeyInput('');setSummary(undefined);setConnected(false);setBusy(false);setLastUpdate(undefined);setIntervalSeconds(0);setError('');onReadings(undefined);
 },[onReadings]);
 useEffect(()=>()=>{generation.current++;pending.current?.abort();key.current='';onReadings(undefined);},[onReadings]);
 useEffect(()=>{if(!authenticated&&!key.current)clear();},[authenticated,clear]);
 const refresh=useCallback(async(localKey=key.current)=>{
  if(!consent||inFlight.current)return;
  inFlight.current=true;const revision=++generation.current;pending.current?.abort();const controller=new AbortController();pending.current=controller;
  setBusy(true);setError('');
  try{
   const params=new URLSearchParams({days:'7',selected_date:day,timezone_name:zone,consent:'true'});
   const result=await requestHealthConnect<HealthSummary>('/wearables/health-connect/summary?'+params,localKey,controller.signal);
   if(revision!==generation.current)return;
   setSummary(result);setLastUpdate(result.fetched_at);setConnected(true);onReadings(watchDataFromHealthConnect(result));
  }catch(e){if(revision===generation.current){setError(e instanceof Error?e.message:'Health Connect could not be read.');setSummary(undefined);setConnected(false);setIntervalSeconds(0);onReadings(undefined);}}
  finally{if(revision===generation.current){setBusy(false);pending.current=null;inFlight.current=false;}}
 },[consent,day,zone,onReadings]);
 useEffect(()=>{if(!connected||!consent||!interval)return;const timer=window.setInterval(()=>{if(!document.hidden)void refresh();},interval*1000);return()=>window.clearInterval(timer);},[connected,consent,interval,refresh]);
 function connect(){key.current=keyInput.trim()||key.current;setKeyInput('');void refresh(key.current);}
 function selectDay(value:string){if(!value)return;generation.current++;pending.current?.abort();pending.current=null;inFlight.current=false;setBusy(false);setDay(value);setSummary(undefined);setLastUpdate(undefined);onReadings(undefined);setError('');}
 return <section className="health-connect-panel" aria-label="Health Connect metrics">
  <header><div><h3>Health Connect</h3><p>Your phone’s recorded measurements</p></div><span>{busy?'Reading…':connected?'Connected':'Not paired'}</span></header>
  {!connected&&<div className="health-connect-pair">
   <label htmlFor="health-pair-key">Local pairing key{authenticated&&<small> · optional when using Cognito</small>}</label>
   <input id="health-pair-key" type="password" autoComplete="off" value={keyInput} onChange={e=>setKeyInput(e.target.value)} placeholder="From your private local pairing file"/>
   <p>Copy from work/health-connect-pairing.txt on this laptop. The key stays in memory and works only for this phone bridge.</p>
  </div>}
  <label className="health-connect-consent"><input type="checkbox" checked={consent} onChange={e=>{setConsent(e.target.checked);if(!e.target.checked)clear();}}/>Allow this session to read my Health Connect records</label>
  <div className="health-connect-controls">
   <label>Day<input type="date" value={day} min={localDateKey(oldest)} max={today} disabled={busy} onChange={e=>selectDay(e.target.value)}/></label>
   <label>Auto-refresh<select value={interval} onChange={e=>setIntervalSeconds(Number(e.target.value))} disabled={!connected||!consent}><option value={0}>Off</option><option value={60}>Every minute</option><option value={120}>Every 2 minutes</option></select></label>
  </div>
  <div className="health-connect-actions"><button disabled={busy||!consent||(!connected&&!keyInput.trim()&&!key.current&&!authenticated)} onClick={()=>connected?void refresh():connect()}><RefreshCw size={15} aria-hidden="true"/>{busy?'Reading…':connected?'Refresh':key.current?'Retry connection':'Connect & read'}</button><button disabled={!connected&&!key.current} onClick={()=>{setConsent(false);clear();}}><Unplug size={15} aria-hidden="true"/>Disconnect & clear</button></div>
  <p className="health-connect-zone">Daily totals: {zone}. Vitals: latest recorded value in the last 7 days.</p>
  {error&&<p role="alert" className="health-connect-error">{error}</p>}
  {!summary&&<p role="status">{busy?'Reading records from your phone…':connected?'Refresh to load this day.':consent?'Connect or refresh to read your phone.':'Readings stay hidden until you allow this session.'}</p>}
  {summary?.retrieval==='phone_cache'&&<p role="status">Cached phone records; this fetch is not a new synchronization. Daily totals may be incomplete.</p>}
  {summary?.warnings.includes('exact_duplicate_records_removed')&&<p>Exact duplicate records were removed before calculating totals.</p>}
  <dl className="health-connect-metrics" aria-busy={busy}>{(Object.keys(metricLabels) as HealthMetricKey[]).map(name=>{
   const metric=summary?.metrics[name],text=metricText(name,metric),available=text!=='No data available';
   return <div key={name} data-metric={name}><dt>{metricLabels[name]}</dt><dd className={available?'has-reading':'no-reading'}>{text}{available&&name!=='sleep'&&<small>{metric?.unit==='count'?'steps':metric?.unit}</small>}</dd>
    <p>{metricNote(metric)}</p>{metric?.timestamp&&<time dateTime={metric.timestamp}>{new Date(metric.timestamp).toLocaleString()}</time>}
    {name==='calories_burned'&&summary?.calorie_basis&&<p>{summary.calorie_basis==='total'?'Total recorded energy':'Active recorded energy'} · never added together</p>}
   </div>;
  })}</dl>
  {lastUpdate&&<p className="health-connect-updated">Last successful update: <time dateTime={lastUpdate}>{new Date(lastUpdate).toLocaleString()}</time></p>}
  {summary?.last_synchronization_at&&<p>Phone last sync: {new Date(summary.last_synchronization_at).toLocaleString()}</p>}
  {!!summary?.skipped_records&&<p>{summary.skipped_records} invalid records were skipped. Affected totals may be unavailable.</p>}
  <p className="health-connect-privacy"><ShieldCheck size={14} aria-hidden="true"/>Read-only. No cloud upload or permanent health-record storage. Missing readings do not imply missing permissions.</p>
 </section>;
}
