import {Component,Suspense,lazy,useCallback,useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {Activity,ArrowLeft,ArrowRight,Battery,Heart,Home,Moon,Settings,ShieldCheck,Wind,Bell,Pause,Play} from 'lucide-react';
import {pageAfter,pageSummary,watchPages,type WatchData,type WatchSettings} from './watchData';
import {WatchBluetooth,type BluetoothState} from './watchBluetooth';
import './watch.css';
const WatchScene=lazy(()=>import('./WatchScene'));
const icons=[Home,Heart,Activity,Moon,Wind,Bell,Settings];
class RenderBoundary extends Component<{children:ReactNode;fallback:ReactNode;onFailure:()=>void},{failed:boolean}>{
 state={failed:false};componentDidCatch(){this.props.onFailure();}static getDerivedStateFromError(){return{failed:true};}render(){return this.state.failed?this.props.fallback:this.props.children;}
}
function FallbackWatch(){return <div className="eco-watch-fallback"><svg viewBox="0 0 220 440" role="img" aria-label="Static fallback of original watch with complete straps"><rect x="73" y="12" width="74" height="416" rx="27" fill="#233b45"/>{[30,45,60,75,350,365,380,395].map(y=><rect key={y} x="104" y={y} width="12" height="5" rx="2" fill="#09151d"/>)}<rect x="37" y="131" width="148" height="176" rx="30" fill="#526774"/><rect x="42" y="136" width="138" height="166" rx="26" fill="#050c12"/><circle cx="110" cy="219" r="42" fill="none" stroke="#58ddeb" strokeWidth="5"/><text x="110" y="226" textAnchor="middle" fill="white" fontSize="24">ECO</text><rect x="185" y="182" width="10" height="28" rx="4" fill="#7796a7"/></svg><p>3D unavailable. Screen controls and connection details remain available below.</p></div>;}

export default function SmartwatchShowcase({data:provided}:{data?:WatchData}){
 const [readings,setReadings]=useState<WatchData>(),[connection,setConnection]=useState<BluetoothState>('disconnected');
 const [consent,setConsent]=useState(false),[connectionError,setConnectionError]=useState(''),[clock,setClock]=useState(Date.now());
 const bluetooth=useMemo(()=>new WatchBluetooth(value=>{setReadings(value);setClock(Date.now());},setConnection,setConnectionError),[]);
 useEffect(()=>()=>bluetooth.disconnect(),[bluetooth]);
 useEffect(()=>{if(connection!=='connected'&&!provided)return;const timer=setInterval(()=>setClock(Date.now()),5000);return()=>clearInterval(timer);},[connection,provided]);
 const incoming=readings||provided;
 const freshHeart=Boolean(incoming?.heartRateAt&&clock-Date.parse(incoming.heartRateAt)<60000&&clock-Date.parse(incoming.heartRateAt)>=-5000);
 const freshBattery=Boolean(incoming?.batteryAt&&clock-Date.parse(incoming.batteryAt)<300000);
 const currentSteps=incoming?.reportedAt?.slice(0,10)===new Date(clock).toISOString().slice(0,10);
 const fromHealthConnect=incoming?.source==='health_connect';
 const data=incoming?{...incoming,heartRate:fromHealthConnect||freshHeart?incoming.heartRate:undefined,battery:freshBattery?incoming.battery:undefined,steps:fromHealthConnect||currentSteps?incoming.steps:undefined}:undefined;
 const status=connection==='connecting'?'CONNECTING':fromHealthConnect?'HEALTH CONNECT RECORDS':incoming?.source==='backend'?'RECORDED READING':freshHeart?'READING RECEIVED':connection==='connected'||incoming?'WAITING FOR READING':'NOT CONNECTED';
 const [page,setPage]=useState(0),[failed,setFailed]=useState(false),[ready,setReady]=useState(false);
 const [settings,setSettings]=useState<WatchSettings>({accent:'#ff914d',brightness:100,motion:true,previewAlerts:true});
 const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 const [visible,setVisible]=useState(true),[active,setActive]=useState(!document.hidden);
 const [tilt,setTilt]=useState({x:0,y:0});const host=useRef<HTMLDivElement>(null);const swipe=useRef<{x:number;y:number}|null>(null);
 useEffect(()=>{const query=window.matchMedia('(prefers-reduced-motion: reduce)');const change=()=>setReduced(query.matches);query.addEventListener('change',change);const visibility=()=>setActive(!document.hidden);document.addEventListener('visibilitychange',visibility);const observer=new IntersectionObserver(([entry])=>setVisible(entry.isIntersecting),{threshold:.05});if(host.current)observer.observe(host.current);return()=>{query.removeEventListener('change',change);document.removeEventListener('visibilitychange',visibility);observer.disconnect();};},[]);
 const next=useCallback(()=>setPage(p=>pageAfter(p,1)),[]),home=useCallback(()=>setPage(0),[]);
 const fail=useCallback(()=>setFailed(true),[]),loaded=useCallback(()=>setReady(true),[]);
 const animate=settings.motion&&!reduced&&visible&&active;
 return <section className="eco-watch" aria-label="EcoRoute 3D smartwatch preview">
  <div className="ew:flex ew:items-center ew:justify-between eco-watch-eyebrow"><span>ECOROUTE / PULSE</span><span className="eco-watch-demo">{status}</span></div>
  <div className="eco-watch-title"><div><h3>Your rhythm.<br/><span>Your journey.</span></h3><p>An original wearable concept</p></div><Battery size={20}/></div>
  <div className="eco-watch-connection">
   <label><input type="checkbox" checked={consent} onChange={e=>{setConsent(e.target.checked);if(!e.target.checked)bluetooth.disconnect();}}/>Allow this browser to read my watch over Bluetooth</label>
   <div><button disabled={!consent||connection!=='disconnected'} onClick={()=>void bluetooth.connect()}>Connect Bluetooth</button><button disabled={connection==='disconnected'} onClick={()=>{bluetooth.disconnect();setConnectionError('');}}>Disconnect & clear</button></div>
   <p>Standard heart-rate sensors only. No health readings are uploaded or saved by this connection.</p>
   {incoming?.heartRateAt&&<p>{fromHealthConnect||incoming.source==='backend'?'Last heart-rate observation reported':'Last heart-rate packet received'}: {new Date(incoming.heartRateAt).toLocaleString()}{!freshHeart?fromHealthConnect?' · older recorded observation':' · stale; no current reading':''}</p>}
   {incoming?.reportedAt&&<p>{fromHealthConnect?'Health Connect fetched':'Backend record reported'}: {new Date(incoming.reportedAt).toLocaleString()}. {fromHealthConnect?`Selected day: ${incoming.selectedDate}. Values are recorded measurements, not continuous watch sensing.`:'Read latest measurement to refresh.'}</p>}
   {connection==='connected'&&!incoming?.heartRateAt&&<p role="status">Connected. Waiting for the watch to report a heart-rate reading.</p>}
   {connectionError&&<p role="status">{connectionError}</p>}
  </div>
  <div ref={host} className="eco-watch-viewport" data-renderer={failed?'fallback':ready?'three':'loading'} data-motion={animate?'active':'paused'}
   onPointerDown={event=>{swipe.current={x:event.clientX,y:event.clientY};}}
   onPointerMove={event=>{if(reduced)return;const box=event.currentTarget.getBoundingClientRect();setTilt({x:Math.max(-1,Math.min(1,(event.clientX-box.left)/box.width*2-1)),y:Math.max(-1,Math.min(1,(event.clientY-box.top)/box.height*2-1))});}}
   onPointerUp={event=>{if(swipe.current){const dx=event.clientX-swipe.current.x,dy=event.clientY-swipe.current.y;if(Math.abs(dx)>45&&Math.abs(dx)>Math.abs(dy))setPage(p=>pageAfter(p,dx<0?1:-1));}swipe.current=null;}}
   onPointerCancel={()=>{swipe.current=null;}} onPointerLeave={()=>{setTilt({x:0,y:0});swipe.current=null;}}>
   <div className="eco-watch-orbit" aria-hidden="true"/>
   {failed?<FallbackWatch/>:<RenderBoundary onFailure={fail} fallback={<FallbackWatch/>}><Suspense fallback={<div className="eco-watch-loading" role="status">Preparing your watch…</div>}><WatchScene data={data} page={watchPages[page]} settings={settings} animate={animate} tilt={reduced?{x:0,y:0}:tilt} onNext={next} onHome={home} onFailure={fail} onReady={loaded}/></Suspense></RenderBoundary>}
   <span className="eco-watch-drag">Move to rotate · tap screen to explore</span>
  </div>
  <div className="eco-watch-navigation ew:flex ew:items-center ew:justify-between"><button aria-label="Previous watch screen" onClick={()=>setPage(p=>pageAfter(p,-1))}><ArrowLeft size={16}/></button><span>{watchPages[page]} <small>{page+1} / {watchPages.length}</small></span><button aria-label="Next watch screen" onClick={next}><ArrowRight size={16}/></button></div>
  <div className="eco-watch-tabs" role="group" aria-label="Watch screens">{watchPages.map((name,i)=>{const Icon=icons[i];return <button key={name} title={name} aria-label={`Watch ${name}`} aria-pressed={page===i} onClick={()=>setPage(i)}><Icon size={17}/></button>;})}</div>
  <p className="eco-watch-readout" aria-live="polite">{pageSummary(watchPages[page],data)}</p>
  {watchPages[page]==='Settings'&&<div className="eco-watch-settings">
   <label>Screen theme<select value={settings.accent} onChange={e=>setSettings(s=>({...s,accent:e.target.value}))}><option value="#ff914d">Transit · orange</option><option value="#58ddeb">Glacier · cyan</option><option value="#b0ef75">Volt · green</option></select></label>
   <label>Brightness · {settings.brightness}%<input aria-label="Watch brightness" type="range" min="35" max="100" value={settings.brightness} onChange={e=>setSettings(s=>({...s,brightness:Number(e.target.value)}))}/></label>
   <label className="eco-watch-toggle"><span>Notification preview</span><input type="checkbox" checked={settings.previewAlerts} onChange={e=>setSettings(s=>({...s,previewAlerts:e.target.checked}))}/></label>
  </div>}
  <div className="eco-watch-actions"><button aria-label="Watch crown home" onClick={home}><Home size={13}/>Home</button><button aria-pressed={!settings.motion} onClick={()=>setSettings(s=>({...s,motion:!s.motion}))}>{settings.motion?<Pause size={13}/>:<Play size={13}/>} {settings.motion?'Pause motion':'Resume motion'}</button></div>
  <div className="eco-watch-disclaimer"><ShieldCheck size={14}/><span>{incoming?'Only received fields are displayed. Heart rate does not measure pollution exposure; no health score is inferred.':'No watch readings available. Connect a supported sensor or an authorized device bridge.'}</span></div>
 </section>;
}
