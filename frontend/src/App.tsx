import HealthConnectPanel from './wearable/HealthConnectPanel';
/* THESIS: A city observatory that makes route exposure legible, not a generic analytics grid.
OWN-WORLD: Silver architectural canvas, charcoal instrument rail, porcelain glass and transit orange.
STORY: Explore a city, open genuine road routes, compare time and estimated exposure, then connect live.
FIRST VIEWPORT: Narrow left metrics, floating pill navigation, large 3D plaza, right route planner.
FORM: User-pinned Axle reference composition; confirmed city-first with side planner. No random direction. */
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownUp, ArrowUpRight, Bell, Bike, Car, Check, ChevronDown, Footprints, Layers, Leaf, LoaderCircle, MapPin, Menu, Minus, Navigation, Pause, Play, Plus, RotateCcw, Settings2, ShieldCheck, Sparkles, Watch, Wind, X } from 'lucide-react';
import { capturedAt, historical, number, projectRoutes, weightedConcentration, type Comparison, type Route } from './data';
import { config, finishSignIn, request, signedIn, signIn, signOut } from './api';
import GoogleMap, { mapsKey } from './GoogleMap';
import JourneyMetrics from './JourneyMetrics';
import {routeColor} from './routeStyle';
import {explanationLabel,type RouteExplanation} from './routeInsight';
import RoutePreferences,{defaultPreferences,compatiblePreferences,type ForecastChoice} from './RoutePreferences';
import {locationInput} from './mapGeometry';
import CinematicCity from './CinematicCity';
import {watchDataFromLatest,type WatchData} from './wearable/watchData';
const SmartwatchShowcase=lazy(()=>import('./wearable/SmartwatchShowcase'));
let completion: Promise<boolean> | undefined;
const tabs=['City overview','Air quality','Journeys','Wearable','Insights'] as const;
type Tab=typeof tabs[number];
const localTime=(date:Date)=>new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);

function RouteMap({routes,selected,onSelect,live}:{routes:Route[];selected:string;onSelect:(id:string)=>void;live:boolean}) {
  const projected=projectRoutes(routes);
  return <div className="route-map"><svg viewBox="0 0 1000 660" role="img" aria-label="Actual provider route geometry, longitude and latitude projected to a local plane">
    <defs><pattern id="map-grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M 50 0 L 0 0 0 50" fill="none" stroke="#acb8b8" strokeWidth=".6"/></pattern></defs>
    <rect width="1000" height="660" fill="url(#map-grid)"/>
    {routes.map((route,i)=><polyline key={route.route_id} points={projected[i].map(p=>p.join(',')).join(' ')} fill="none" stroke={routeColor(i)} strokeWidth={route.route_id===selected?7:4} strokeLinecap="round" strokeLinejoin="round" onClick={()=>onSelect(route.route_id)}/>)}
    {projected[0]?.length>0&&[projected[0][0],projected[0].at(-1)!].map((p,i)=><g key={i}><circle cx={p[0]} cy={p[1]} r="13" fill={i?'#ff702d':'#25292b'} stroke="#fff" strokeWidth="4"/><text x={p[0]+24} y={p[1]+5} fill="#202628" fontSize="18" fontWeight="600">{i?'Destination':'Origin'}</text></g>)}
  </svg><div className="map-caption"><Navigation size={16}/><span>Actual road geometry · no geographic basemap<br/><small>{live ? "Resolution varies by source. Review the returned source metadata." : "Pollution resolution is approximately 45 km, not street level."}</small></span></div></div>;
}

export default function App() {
  const [tab,setTab]=useState<Tab>('City overview');const [view,setView]=useState<'city'|'route'>(mapsKey?'route':'city');
  const [moving,setMoving]=useState(!matchMedia('(prefers-reduced-motion: reduce)').matches);const [zoom,setZoom]=useState(0);const [reset,setReset]=useState(0);
  const [comparison,setComparison]=useState<Comparison|null>(mapsKey?null:historical);const [selected,setSelected]=useState(mapsKey?'':historical.selected_route_id);
  const [live,setLive]=useState(!!mapsKey);const [authenticated,setAuthenticated]=useState(signedIn());
  const [origin,setOrigin]=useState(mapsKey?'':'India Gate, New Delhi');const [destination,setDestination]=useState(mapsKey?'':'Connaught Place, New Delhi');
  const [mode,setMode]=useState('driving');const [objective,setObjective]=useState('balanced');const [departure,setDeparture]=useState(localTime(new Date(Date.now()+600000)));
  const [preferences,setPreferences]=useState(defaultPreferences);const [forecast,setForecast]=useState<ForecastChoice>(null);
  const [consent,setConsent]=useState(false);const [detour,setDetour]=useState(25);const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');
  const [drawer,setDrawer]=useState<'connection'|'alerts'|null>(null);const [serviceData,setServiceData]=useState<unknown>(null);
  const [deviceId,setDeviceId]=useState('');const [explanation,setExplanation]=useState('');const [panel,setPanel]=useState(!!mapsKey);
  const [explanationMeta,setExplanationMeta]=useState<RouteExplanation>();
  const lastRequest=useRef<Record<string,unknown>|undefined>(undefined);
  const currentRoute=useRef('');
  const [wearableData,setWearableData]=useState<WatchData>();
  useEffect(()=>{if(!authenticated){setWearableData(undefined);setForecast(null);}},[authenticated]);
  const [routeLabels,setRouteLabels]=useState({origin:'India Gate, New Delhi',destination:'Connaught Place, New Delhi'});
  const [chosenLocations,setChosenLocations]=useState<{origin?:google.maps.LatLngLiteral;destination?:google.maps.LatLngLiteral}>({});
  const dialogRef=useRef<HTMLElement>(null);
  useEffect(()=>{if(!drawer)return;const previous=document.querySelector<HTMLElement>(drawer==='connection'?'[aria-label="Connection settings"]':'[aria-label="Alerts"]');const oldOverflow=document.body.style.overflow;document.body.style.overflow='hidden';
    const trap=(event:KeyboardEvent)=>{if(event.key==='Escape'){setDrawer(null);return;}if(event.key!=='Tab')return;const elements=Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href]')||[]);const first=elements[0],last=elements.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}};
    document.addEventListener('keydown',trap);return()=>{document.removeEventListener('keydown',trap);document.body.style.overflow=oldOverflow;previous?.focus();};},[drawer]);
  useEffect(()=>{let active=true;completion ||= finishSignIn();completion.then(ok=>{if(active&&ok){setAuthenticated(true);setNotice('Signed in. Switch to live services to compare a new journey.');}}).catch(e=>{if(active)setNotice(e.message);});return()=>{active=false;};},[]);
  useEffect(()=>{const listener=()=>{if(matchMedia('(prefers-reduced-motion: reduce)').matches)setMoving(false);};const media=matchMedia('(prefers-reduced-motion: reduce)');media.addEventListener('change',listener);return()=>media.removeEventListener('change',listener);},[]);
  const routes=comparison?.routes||[];const selectedRoute=routes.find(r=>r.route_id===selected)||routes[0];
  currentRoute.current=selectedRoute?.route_id||'';
  const selectRoute=useCallback((id:string)=>{if(!routes.some(route=>route.route_id===id))return;setSelected(id);setExplanation('');setServiceData(null);},[routes]);
  const displayPoint=selectedRoute?.geometry.coordinates[0]||(chosenLocations.origin?[chosenLocations.origin.lng,chosenLocations.origin.lat]:undefined);
  const locationTitle=live?(routes.length?routeLabels.origin:origin||'Choose a location'):'New Delhi';
  const pm=weightedConcentration(selectedRoute);const coverage=selectedRoute?Math.round(selectedRoute.pm25_coverage_fraction*100):null;
  async function action(task:()=>Promise<void>){setNotice('');setBusy(true);try{await task();}catch(e){setNotice(e instanceof Error?e.message:'This service is unavailable.');setAuthenticated(signedIn());}finally{setBusy(false);}}
  function changeTab(next:Tab){setTab(next);setPanel(true);setServiceData(null);setExplanation('');if(next==='Journeys')setView('route');}
  function changeMode(value:boolean){setLive(value);setComparison(value?null:historical);setSelected(value?'':historical.selected_route_id);setServiceData(null);setExplanation('');setNotice('');setMode('driving');setChosenLocations({});if(value){setOrigin('');setDestination('');}if(!value){setOrigin('India Gate, New Delhi');setDestination('Connaught Place, New Delhi');setRouteLabels({origin:'India Gate, New Delhi',destination:'Connaught Place, New Delhi'});}}
  function chooseMapLocation(kind:'origin'|'destination',point:{lat:number;lng:number}){
    if(!live)changeMode(true);
    const value=`${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`;
    if(kind==='origin')setOrigin(value);else setDestination(value);
    setChosenLocations(previous=>({...previous,[kind]:point}));
    setComparison(null);setSelected('');setPanel(true);setTab('Journeys');
    setNotice(`${kind==='origin'?'Start':'Destination'} selected on the map. Compare your journey to request a road route.`);
  }
  function selectTravelMode(next:string){
    setMode(next);setServiceData(null);setExplanation('');setNotice('');
    if(!live){setComparison(next==='driving'?historical:null);setSelected(next==='driving'?historical.selected_route_id:'');}
    else{setComparison(null);setSelected('');}
  }
  async function compare(){
    if(mode==='cycling'&&!live){setNotice('Switch to Live services and configure the cycling provider. Google does not list bicycle-direction coverage for India.');return;}
    if(!live&&mode==='walking'){setNotice('Walking requires live routing. Open Connection settings and choose Live services. The saved preview contains driving routes only.');return;}
    if(!live){setView('route');setPanel(true);setSelected(historical.recommended_route_ids[objective]||historical.selected_route_id);setNotice('Showing the saved Delhi comparison from 9 October 2026. These are not current conditions.');return;}
    if(!consent){setNotice('Confirm location processing before comparing.');return;}
    await action(async()=>{const body={origin:locationInput(origin),destination:locationInput(destination),mode,objective,departure_at:new Date(departure).toISOString(),max_detour_percent:detour,...compatiblePreferences(preferences,mode),max_alternatives:2,segment_length_m:250,consent_to_store:authenticated,...(authenticated&&forecast?forecast:{})};const result=await request<Comparison>(authenticated&&forecast?'/routes/predict':authenticated?'/routes/compare':'/routes/preview',body,authenticated);if(!Array.isArray(result.routes))throw new Error('The backend returned an unexpected route format.');lastRequest.current={...body,...(result.resolved_origin?{origin:{longitude:result.resolved_origin[0],latitude:result.resolved_origin[1]}}:{}),...(result.resolved_destination?{destination:{longitude:result.resolved_destination[0],latitude:result.resolved_destination[1]}}:{})};setComparison(result);setSelected(result.selected_route_id);setExplanation('');setRouteLabels({origin,destination});setView('route');});
  }
  async function explainComparison(){
    if(!live){setExplanationMeta(undefined);setExplanation(routeSummary());return;}
    const routeId=selectedRoute?.route_id, routeIndex=routes.indexOf(selectedRoute!);
    await action(async()=>{
      if(comparison?.persistence==='request_only'){
        if(!lastRequest.current)throw new Error('Compare this journey again before requesting an explanation.');
        const result=await request<Comparison>('/routes/preview',{...lastRequest.current,consent_to_store:false,include_explanation:true},false);
        if(currentRoute.current!==routeId)return; // Selection changed while the request was running.
        if(!result.explanation||!Array.isArray(result.routes))throw new Error('The backend did not return an explanation.');
        setComparison(result);setSelected(result.routes[routeIndex]?.route_id||result.selected_route_id);
        setExplanation(result.explanation.explanation);setExplanationMeta(result.explanation);
      }else{
        const value=await request<RouteExplanation>('/ai/explain-route',{route_ids:routes.map(r=>r.route_id)});
        if(currentRoute.current!==routeId)return;
        setExplanation(value.explanation);setExplanationMeta(value);
      }
    });
  }
  function routeSummary(){return selectedRoute?`${number(selectedRoute.duration_s/60)} minutes · ${number(selectedRoute.distance_m/1000)} km. Estimated PM2.5 exposure: ${number(selectedRoute.estimated_pm25_exposure_ug_h_m3,3)} µg·h/m³. ${selectedRoute.estimated_pm25_exposure_ug_h_m3===null?'Coverage is incomplete.':'Exposure combines concentration and travel time.'} This coarse model cannot establish precise street-level differences.`:'Compare a route to see an explanation supported by its metrics.';}
  const sharedTitle=tab==='City overview'||tab==='Journeys';
  return <div className="app-shell">
    <aside className="instrument-rail" aria-label="Journey metrics">
      <div className="brand-panel"><a className="brand" href="#" aria-label="EcoRoute home" onClick={e=>{e.preventDefault();changeTab('City overview');setView('city');}}><span className="brand-mark">↗</span><span>EcoRoute AI<small>INTELLIGENCE IN MOTION</small></span></a><div className="location"><span className="signal-dot"/><span>{locationTitle}</span><ChevronDown size={14}/></div><div className="rail-title">A better way<br/>through the city.</div><span className="rail-small">{displayPoint?`${Math.abs(displayPoint[1]).toFixed(4)}° ${displayPoint[1]>=0?'N':'S'} ${Math.abs(displayPoint[0]).toFixed(4)}° ${displayPoint[0]>=0?'E':'W'}`:'Select your start and destination'}</span></div>
      <JourneyMetrics route={selectedRoute} routeIndex={routes.indexOf(selectedRoute!)} live={live} sharedForecast={comparison?.spatial_differentiation==='not_resolved_same_model_cell'}/>
      <button className="rail-footer" onClick={()=>setDrawer('connection')}><ShieldCheck size={17}/><span>Private by design</span><ArrowUpRight size={14}/></button>
    </aside>
    <main className="workspace">
      <header className="topbar"><button className="circle-button menu-toggle" aria-label={panel?'Hide detail panel':'Show detail panel'} onClick={()=>setPanel(!panel)}><Menu size={21}/></button><nav aria-label="Dashboard sections">{tabs.map(t=><button disabled={busy} key={t} className={tab===t?'nav-pill active':'nav-pill'} onClick={()=>changeTab(t)}>{t}</button>)}</nav><div className="top-actions"><button className="circle-button" aria-label="Alerts" onClick={()=>{setDrawer('alerts');setServiceData(null);}}><Bell size={19}/></button><button className="circle-button" aria-label="Connection settings" onClick={()=>setDrawer('connection')}><Settings2 size={19}/></button></div></header>
      <section className={`city-stage ${panel?'panel-open':''} mode-${view} ${tab==='Wearable'?'wearable-active':''}`} aria-label="City observatory">
        {view==='city'&&<CinematicCity moving={moving} zoom={zoom} reset={reset}/>}
        {view==='route'&&(mapsKey||live?<GoogleMap routes={routes} selected={selected} onSelect={selectRoute} live={live} originLabel={routes.length?routeLabels.origin:origin} destinationLabel={routes.length?routeLabels.destination:destination} chosenLocations={live?chosenLocations:undefined} onChooseLocation={chooseMapLocation}/>:<RouteMap live={live} routes={routes} selected={selected} onSelect={selectRoute}/>)}
        <div className="stage-shade"/>
        <div className="view-controls"><button className={view==='city'?'selected':''} onClick={()=>setView('city')}><Layers size={15}/>City view</button><button className={view==='route'?'selected':''} onClick={()=>{setView('route');setPanel(true);}}><Navigation size={15}/>Route view</button></div>
        {view!=='route'&&<div className="scene-tools"><button aria-label="Zoom in" onClick={()=>setZoom(z=>Math.min(z+1,4))}><Plus size={19}/></button><button aria-label="Zoom out" onClick={()=>setZoom(z=>Math.max(z-1,-3))}><Minus size={19}/></button><span/><button aria-label="Reset camera" onClick={()=>{setReset(r=>r+1);setZoom(0);}}><RotateCcw size={17}/></button><button aria-label={moving?'Pause city motion':'Play city motion'} onClick={()=>setMoving(!moving)}>{moving?<Pause size={16}/>:<Play size={16}/>}</button></div>}
        {view==='city'&&<div className="city-hotspots"><button className="city-hotspot transit" aria-label="Open journey planner" onClick={()=>{setTab('Journeys');setPanel(true);}}><Navigation size={19}/></button><button className="city-hotspot environment" aria-label="Explore air quality" onClick={()=>changeTab('Air quality')}><Leaf size={19}/></button></div>}
        <div className="hero-copy"><span>LESS EXPOSURE. MORE PERSPECTIVE.</span><h1>Your city.<br/>More possibility.</h1></div>
        {panel&&<aside className={`detail-panel ${tab==='Wearable'?'wearable-panel':''}`} aria-label="Journey planner">
          <div className="panel-heading"><div><span className="overline">{sharedTitle?'LET’S GET YOU THERE':tab==='Air quality'?'UNDERSTAND THE AIR':'YOUR ECOROUTE'}</span><h2>{sharedTitle?'Your next journey':tab}</h2></div><span className="panel-icon">{sharedTitle?<ArrowUpRight size={24}/>:tab==='Wearable'?<Watch size={24}/>:<Wind size={24}/>}</span></div>
          {sharedTitle?<><form onSubmit={e=>{e.preventDefault();void compare();}}>
            <div className="location-fields"><label><span className="origin-dot"/><span><small>FROM</small><input aria-label="Origin" placeholder="Choose a start or enter an address" autoComplete="off" value={origin} readOnly={!live} required minLength={3} onChange={e=>{setOrigin(e.target.value);setChosenLocations(v=>({...v,origin:undefined}));}}/></span></label><div className="field-divider"/><label><MapPin size={15}/><span><small>TO</small><input aria-label="Destination" placeholder="Choose a destination or enter an address" autoComplete="off" value={destination} readOnly={!live} required minLength={3} onChange={e=>{setDestination(e.target.value);setChosenLocations(v=>({...v,destination:undefined}));}}/></span></label>{live&&<button type="button" className="swap" aria-label="Swap origin and destination" onClick={()=>{setOrigin(destination);setDestination(origin);setChosenLocations(v=>({origin:v.destination,destination:v.origin}));}}><ArrowDownUp size={15}/></button>}</div>
            <div className="travel-modes" aria-label="Travel mode">{[{id:'driving',icon:Car,name:'Drive'},{id:'walking',icon:Footprints,name:'Walk'},{id:'cycling',icon:Bike,name:'Cycle'}].map(m=><button key={m.id} type="button" disabled={busy} aria-pressed={mode===m.id} className={mode===m.id?'chosen':''} onClick={()=>selectTravelMode(m.id)}><m.icon size={17}/>{m.name}</button>)}</div>
            {mode==='cycling'&&<p className="note" role="status">Cycling requires an openrouteservice connection. Google bicycle directions are not listed for India.</p>}
            {mode==='walking'&&!live&&<p className="note">Walking routes need live services. <button type="button" className="inline-connection" onClick={()=>setDrawer('connection')}>Connect routing</button></p>}
            <label className="field-label">Departure{live?<input aria-label="Departure" type="datetime-local" value={departure} required onChange={e=>setDeparture(e.target.value)}/>:<span className="recorded-departure">{new Date(routes[0]?.departure_at||capturedAt).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'})}</span>}</label>
            <div className="objective-row"><label className="field-label">Preference<select value={objective} onChange={e=>setObjective(e.target.value)}><option value="balanced">Balanced</option><option value="fastest">Fastest</option><option value="lowest_exposure">Lowest exposure</option></select></label>{live&&<label className="field-label">Max. detour<select value={detour} onChange={e=>setDetour(Number(e.target.value))}><option value={10}>10%</option><option value={25}>25%</option><option value={50}>50%</option></select></label>}</div>
            {live&&<RoutePreferences mode={mode} value={preferences} onChange={setPreferences} authenticated={authenticated} forecast={forecast} onForecast={setForecast}/>}
            {live&&<label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>Allow processing my locations and route. Google routes are not saved.</label>}
            <button className="primary-button" disabled={busy} type="submit">{busy?<LoaderCircle className="spin" size={17}/>:<Navigation size={17}/>} {live||mode!=='driving'?'Compare routes':'Explore recorded routes'}<ArrowUpRight size={17}/></button>
          </form><div className="section-divider"><span>YOUR OPTIONS</span><small>{routes.length} routes</small></div>
          <div className="route-options">{routes.map((route,i)=><button key={route.route_id} className={`route-option ${selected===route.route_id?'chosen':''}`} aria-pressed={selectedRoute?.route_id===route.route_id} onClick={()=>{selectRoute(route.route_id);setView('route');}}>{['google_routes','openrouteservice'].some(provider=>provider===route.routing_source.provider)&&<span className="google-attribution">{route.routing_source.provider==='google_routes'?'Google Maps':'openrouteservice / © OpenStreetMap contributors'}</span>}<span className="route-option-top"><span><span className={`route-dot route-${i}`} style={{background:routeColor(i)}}/>{route.route_id===comparison?.recommended_route_ids.fastest?'Fastest route':'Alternative route'}</span>{selected===route.route_id?<Check size={16}/>:<ArrowUpRight size={15}/>}</span><span className="route-figures"><strong>{number(route.duration_s/60)}<small> min</small></strong><span>{number(route.distance_m/1000)} km</span></span><span className="route-exposure">{number(route.estimated_pm25_exposure_ug_h_m3,2)} µg·h/m³ <small>estimated exposure</small></span></button>)}</div>{!routes.length&&<p className="empty-copy">Compare your journey. Missing data will be shown as unavailable.</p>}<p className="panel-footnote"><ShieldCheck size={13}/>Coarse forecast · not street-level sensing</p></>:
          tab==='Air quality'?<><div className="big-reading">{number(pm)}<span>µg/m³ PM2.5</span></div><p className="panel-description">{pm===null?'No usable pollution forecast covers this route and departure time. A dash means unavailable, not zero. ':'Time-weighted concentration along the selected route. '}{live?'From returned route data.':'From the saved Open-Meteo / CAMS forecast.'}</p><div className="fact-list"><div><span>Spatial resolution</span><strong>{live?"Source-dependent":"~45 km"}</strong></div><div><span>Coverage</span><strong>{coverage??'—'}{coverage!==null?'%':''}</strong></div><div><span>Confidence</span><strong>{selectedRoute?.confidence||'Unavailable'}</strong></div><div><span>Data type</span><strong>{live?'See source metadata':'Historical forecast'}</strong></div></div><p className="note">Concentrations are not AQI values. Buildings and streets in the city scene are illustrative.</p><button className="primary-button" disabled={busy||!live} onClick={()=>void action(async()=>setServiceData(await request('/data/quality')))}>Check data quality <ArrowUpRight size={17}/></button>{serviceData!=null&&<pre className="data-result">{JSON.stringify(serviceData,null,2)}</pre>}</>:
          tab==='Wearable'?<><HealthConnectPanel authenticated={authenticated} onReadings={setWearableData}/><Suspense fallback={<p role="status">Loading wearable preview…</p>}><SmartwatchShowcase data={wearableData}/></Suspense><h3>Your watch. Your consent.</h3><p className="panel-description">Noise ColorFit Pro3 Alpha<br/>NoiseFit Assist</p><span className="small-badge">Cloud bridge not connected</span><p className="note">The phone bridge reads Health Connect records; this does not verify Noise vendor sensor access. Standard Bluetooth sensors can also connect; cloud storage requires Cognito and device consent. Heart rate is not a direct measure of pollution exposure.</p><label className="field-label">Registered device ID<input value={deviceId} onChange={e=>{setDeviceId(e.target.value);setWearableData(undefined);setServiceData(null);}} placeholder="Your owned device ID"/></label><button className="primary-button" disabled={busy||!live||!deviceId} onClick={()=>void action(async()=>{const result=await request('/wearables/latest?device_id='+encodeURIComponent(deviceId));setServiceData(result);setWearableData(watchDataFromLatest(result));})}>Read latest measurement <ArrowUpRight size={17}/></button>{serviceData!=null&&<pre className="data-result">{JSON.stringify(serviceData,null,2)}</pre>}</>:
          <><div className="insight-symbol"><Sparkles size={32}/></div><h3>Metrics first.<br/>Meaning, made clear.</h3><p className="panel-description">{routeSummary()}</p><button className="primary-button" disabled={busy||!selectedRoute} onClick={()=>void explainComparison()}>Explain this comparison <ArrowUpRight size={17}/></button>{explanation&&<p className="explanation"><small>{explanationLabel(explanationMeta)}</small>{explanation}</p>}{live&&comparison?.persistence==='request_only'&&<p className="note">Explain refreshes genuine routes before invoking the configured LLM. No route geometry or place names are sent to it.</p>}</>}
        </aside>}
      </section>
    </main>
    {notice&&<div className="notice" role="status"><span>{notice}</span><button aria-label="Dismiss message" onClick={()=>setNotice('')}><X size={18}/></button></div>}
    {drawer&&<div className="drawer-backdrop" onClick={()=>setDrawer(null)}><section ref={dialogRef} className="connection-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Escape')setDrawer(null);}}><button autoFocus className="drawer-close" aria-label="Close dialog" onClick={()=>setDrawer(null)}><X/></button><span className="overline">ECOROUTE AI</span><h2 id="drawer-title">{drawer==='connection'?'Your connection':'Environmental alerts'}</h2>{drawer==='connection'?<><p>The city uses layered architectural artwork with animated trains, reflections and perspective. It is an illustrative 2.5D scene, not a real map of Delhi. The historical preview uses an actual saved Delhi driving comparison from 9 October 2026, not live conditions. Sources: OSRM / OpenStreetMap and Open-Meteo / CAMS.</p><div className="mode-switch"><button disabled={busy} className={!live?'selected':''} onClick={()=>changeMode(false)}>Historical preview</button><button disabled={busy} className={live?'selected':''} onClick={()=>changeMode(true)}>Live services</button></div><p className="note">Guest maps and request-only comparisons do not require sign-in. Private records require Cognito. Live routing needs configured backend providers. It never silently substitutes demo data.</p><div className="fact-list"><div><span>API</span><code>{config.base}</code></div><div><span>Authentication</span><strong>{authenticated?'Signed in':'Not signed in'}</strong></div></div><button className="primary-button" disabled={busy} onClick={()=>void action(async()=>{if(authenticated){signOut();setAuthenticated(false);setComparison(live?null:historical);setServiceData(null);setNotice('Signed out on this device.');}else await signIn();})}>{authenticated?'Sign out':'Sign in with Cognito'}<ArrowUpRight size={17}/></button><button className="secondary-button" disabled={busy} onClick={()=>void action(async()=>{await request('/health',undefined,false);setNotice('Backend health check passed. This does not verify provider access.');})}>Check backend connection</button><p className="note">Tokens stay in memory. No AWS keys belong in the browser. Reloading requires sign-in again.</p></>:<><p>Alerts are opt-in. This preview does not send email or SMS, and no test alert will notify a real recipient.</p><button className="primary-button" disabled={!live||busy} onClick={()=>void action(async()=>setServiceData(await request('/alerts')))}>Read my alerts <ArrowUpRight size={17}/></button>{!live&&<p className="note">Switch to live services and sign in to retrieve your alerts.</p>}{serviceData!=null&&<pre className="data-result">{JSON.stringify(serviceData,null,2)}</pre>}</>}</section></div>}
  </div>;
}
