/// <reference types="google.maps" />
import {useEffect, useRef, useState} from 'react';
import {Compass, Crosshair, Layers, LocateFixed, Minus, Plus, RotateCcw} from 'lucide-react';
import type {Route} from './data';
import {routePath} from './mapGeometry';
import './journey-map.css';
import {routeColor} from './routeStyle';

export const mapsKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
const mapId = import.meta.env.VITE_GOOGLE_MAP_ID || '';
const WORLD = {lat:0, lng:0};
let loading:Promise<void>|undefined;

function loadMaps() {
  if (window.google?.maps?.Map) return Promise.resolve();
  if (loading) return loading;
  loading = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    const fail = (message:string) => {clearTimeout(timer); script.remove(); reject(new Error(message));};
    const timer = setTimeout(() => fail('Google Maps timed out.'), 15000);
    Object.assign(window, {
      ecoGoogleReady:() => {clearTimeout(timer); resolve();},
      gm_authFailure:() => {window.dispatchEvent(new Event('google-map-auth-error')); fail('Google Maps authorization failed.');},
    });
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(mapsKey)}&loading=async&callback=ecoGoogleReady&v=weekly`;
    script.async = true; script.onerror = () => fail('Google Maps could not load.');
    document.head.append(script);
  }).catch(error => {loading = undefined; throw error;});
  return loading;
}

// Google projects the pin's tip onto the actual coordinate. No fabricated map points.
function addPin(map:google.maps.Map, position:google.maps.LatLngLiteral, label:string,
                kind:'origin'|'destination', onPick:()=>void) {
  const button = document.createElement('button'); button.type = 'button';
  button.className = `journey-pin journey-pin-${kind}`;
  button.setAttribute('aria-label', `${kind === 'origin' ? 'Origin' : 'Destination'}: ${label}`);
  const cap = document.createElement('span'); cap.className = 'journey-pin-cap'; cap.textContent = kind === 'origin' ? 'A' : 'B';
  const name = document.createElement('span'); name.className = 'journey-pin-name'; name.textContent = label;
  button.append(cap, name); button.addEventListener('click', onPick);
  class Pin extends google.maps.OverlayView {
    onAdd() {this.getPanes()?.overlayMouseTarget.append(button); google.maps.OverlayView.preventMapHitsAndGesturesFrom(button);}
    draw() {
      const point = this.getProjection()?.fromLatLngToDivPixel(new google.maps.LatLng(position));
      if (point) {button.style.left = `${point.x}px`; button.style.top = `${point.y}px`;}
    }
    onRemove() {button.removeEventListener('click', onPick); button.remove();}
  }
  const pin = new Pin(); pin.setMap(map); return pin;
}

interface Props {
  routes:Route[]; selected:string; onSelect:(id:string)=>void; live?:boolean;
  originLabel?:string; destinationLabel?:string;
  chosenLocations?:{origin?:google.maps.LatLngLiteral; destination?:google.maps.LatLngLiteral};
  onChooseLocation?:(kind:'origin'|'destination', position:google.maps.LatLngLiteral)=>void;
}

export default function GoogleMap({routes, selected, onSelect, live=false,
  originLabel='Start', destinationLabel='Destination', chosenLocations, onChooseLocation}:Props) {
  const host = useRef<HTMLDivElement>(null), map = useRef<google.maps.Map|null>(null);
  const lines = useRef<{route:Route; line:google.maps.Polyline;halo:google.maps.Polyline;index:number}[]>([]), fitted = useRef('');
  const perspectiveRef = useRef(false);
  const pending3D=useRef(false),switchTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
  const [switching3D,setSwitching3D]=useState(false);
  const [ready, setReady] = useState(false), [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0), [perspective, setPerspective] = useState(false);
  const [vector, setVector] = useState<boolean|null>(null), [satellite, setSatellite] = useState(true);
  const [picking, setPicking] = useState<'origin'|'destination'|null>(null);
  const [pinDetail, setPinDetail] = useState<{label:string; position:google.maps.LatLngLiteral}|null>(null);
  const [viewMessage,setViewMessage]=useState('');
  const [locating,setLocating]=useState(false),[locationError,setLocationError]=useState('');
  const active = routes.find(route => route.route_id === selected && routePath(route).length >= 2)
    || routes.find(route => routePath(route).length >= 2);

  useEffect(() => {
    let mounted = true;
    setReady(false); setError(''); setVector(null); setViewMessage(''); fitted.current = '';
    const authError = () => {setReady(false); setError('Google Maps could not authorize this website. Check Maps JavaScript API, billing and website restrictions.');};
    window.addEventListener('google-map-auth-error', authError);
    if (!mapsKey) {
      setError(location.hostname==='localhost'||location.hostname==='127.0.0.1'
        ? 'Configure VITE_GOOGLE_MAPS_API_KEY in frontend/.env.local, then restart the app.'
        : 'Configure VITE_GOOGLE_MAPS_API_KEY in Amplify environment variables, then redeploy this branch. Use a browser key restricted to this website.');
      return () => window.removeEventListener('google-map-auth-error', authError);
    }
    loadMaps().then(() => {
      if (!mounted || !host.current) return;
      map.current = new google.maps.Map(host.current, {
        center:WORLD, zoom:2, tilt:0, heading:0, renderingType:google.maps.RenderingType.VECTOR,
        ...(mapId ? {mapId} : {}), mapTypeId:'hybrid', mapTypeControl:false,
        streetViewControl:false, fullscreenControl:false, zoomControl:false, rotateControl:false,
        cameraControl:false, clickableIcons:true, tiltInteractionEnabled:true,
        headingInteractionEnabled:true, gestureHandling:'cooperative', isFractionalZoomEnabled:true,
      });
      const syncRenderer = () => {
        if (!mounted || !map.current) return;
        const type=map.current.getRenderingType();
        // UNINITIALIZED is a loading state, not evidence that WebGL failed.
        if(type!==google.maps.RenderingType.VECTOR && type!==google.maps.RenderingType.RASTER)return;
        const available=type===google.maps.RenderingType.VECTOR;
        setVector(available);
        if(host.current)host.current.dataset.renderingType=available?'vector':'raster';
        if(!available){setPerspective(false);perspectiveRef.current=false;}
        applyPending3D();
      };
      map.current.addListener('renderingtype_changed', syncRenderer);
      map.current.addListener('idle', syncRenderer);
      map.current.addListener('tilesloaded', () => {
        if(mounted && host.current)host.current.dataset.tilesLoaded='true';
        syncRenderer();
      });
      map.current.addListener('tilt_changed', () => {
        if(!mounted || !map.current)return;
        const tilted=(map.current.getTilt()||0)>0;
        setPerspective(tilted);perspectiveRef.current=tilted;
        if(host.current)host.current.dataset.cameraTilt=String(map.current.getTilt()||0);
      });
      syncRenderer();setReady(true);
    }).catch(() => {if (mounted) setError('Google Maps could not load. Check your connection, key restrictions and billing, then retry.');});
    return () => {
      mounted = false;pending3D.current=false;clearTimeout(switchTimer.current);
      if (map.current) google.maps.event.clearInstanceListeners(map.current);
      map.current = null; host.current?.replaceChildren();
      window.removeEventListener('google-map-auth-error', authError);
    };
  }, [attempt]);

  useEffect(() => {
    if (!ready || !map.current) return;
    const overlays = routes.flatMap((route,index) => {
      const path=routePath(route);if(path.length<2)return [];
      const halo=new google.maps.Polyline({map:map.current,path,strokeColor:'#ffffff',strokeOpacity:.95,strokeWeight:10,zIndex:index*2+1,clickable:false});
      const line=new google.maps.Polyline({map:map.current,path,strokeColor:routeColor(index),strokeOpacity:1,strokeWeight:6,zIndex:index*2+2});
      line.addListener('click',()=>onSelect(route.route_id));return [{route,line,halo,index}];
    });
    lines.current = overlays;
    return () => {overlays.forEach(({line,halo}) => {google.maps.event.clearInstanceListeners(line); line.setMap(null);halo.setMap(null);}); lines.current = [];};
  }, [ready, routes, onSelect]);

  useEffect(() => {
    lines.current.forEach(({route,line,halo,index})=>{
      const chosen=route.route_id===active?.route_id;
      halo.setOptions({strokeWeight:chosen?13:10,zIndex:chosen?31:index*2+1});
      line.setOptions({strokeColor:routeColor(index),strokeOpacity:1,strokeWeight:chosen?9:6,zIndex:chosen?32:index*2+2});
    });
  }, [ready, routes, active?.route_id]);

  useEffect(() => {
    setPinDetail(null);
    if (!ready || !map.current) return;
    const path = active ? routePath(active) : [];
    const positions = path.length ? [path[0], path.at(-1)!] : [chosenLocations?.origin, chosenLocations?.destination];
    const pins = positions.flatMap((position, index) => {
      if (!position) return [];
      const label = index ? destinationLabel : originLabel;
      return [addPin(map.current!, position, label, index ? 'destination' : 'origin', () => setPinDetail({label, position}))];
    });
    return () => pins.forEach(pin => pin.setMap(null));
  }, [ready, active, originLabel, destinationLabel, chosenLocations?.origin?.lat, chosenLocations?.origin?.lng, chosenLocations?.destination?.lat, chosenLocations?.destination?.lng]);

  function fitJourney() {
    if (!map.current) return;
    const points = routes.flatMap(routePath);
    if (!points.length) {const chosen=[chosenLocations?.origin,chosenLocations?.destination].filter((p):p is google.maps.LatLngLiteral=>!!p);if(chosen.length){const bounds=new google.maps.LatLngBounds();chosen.forEach(p=>bounds.extend(p));map.current.fitBounds(bounds,80);return;}map.current.moveCamera({center:WORLD, zoom:2, tilt:0, heading:0}); return;}
    const bounds = new google.maps.LatLngBounds(); points.forEach(point => bounds.extend(point));
    // Preserve intent before fitBounds emits tilt_changed for its overhead reset.
    const wantedTilt=perspectiveRef.current;
    google.maps.event.addListenerOnce(map.current, 'idle', () => {map.current?.moveCamera({tilt:wantedTilt ? 50 : 0, heading:0});});
    map.current.fitBounds(bounds, {top:96, bottom:70, left:65, right:65});
  }
  useEffect(() => {
    const signature = routes.map(route => route.route_id).join('|') || 'world';
    if (!ready || fitted.current === signature) return;
    fitted.current = signature; fitJourney();
  }, [ready, routes]);

  useEffect(() => {
    if (!ready || !map.current || !picking || !onChooseLocation) return;
    const listener = map.current.addListener('click', (event:google.maps.MapMouseEvent) => {
      if (!event.latLng) return;
      onChooseLocation(picking, event.latLng.toJSON()); setPicking(null); setPinDetail(null);
    });
    return () => listener.remove();
  }, [ready, picking, onChooseLocation]);

  useEffect(()=>{
    if(!ready||!map.current||active)return;
    if(chosenLocations?.origin&&chosenLocations?.destination){fitJourney();return;}
    const point=chosenLocations?.origin||chosenLocations?.destination;
    if(point)map.current.moveCamera({center:point,zoom:Math.max(15,map.current.getZoom()||2),tilt:perspectiveRef.current?50:0});
  },[ready,active,chosenLocations?.origin?.lat,chosenLocations?.origin?.lng,chosenLocations?.destination?.lat,chosenLocations?.destination?.lng]);

  function useMyLocation(){
    if(!navigator.geolocation){setLocationError('Your browser does not support location access. Choose a point or enter an address.');return;}
    setLocating(true);setLocationError('');
    navigator.geolocation.getCurrentPosition(position=>{
      const point={lat:position.coords.latitude,lng:position.coords.longitude};
      onChooseLocation?.('origin',point);map.current?.moveCamera({center:point,zoom:16,tilt:perspectiveRef.current?50:0});setLocating(false);
    },()=>{setLocating(false);setLocationError('Location access was unavailable. Choose a point or enter an address instead.');},{enableHighAccuracy:false,timeout:10000,maximumAge:60000});
  }
  function cancel3DSwitch(){
    pending3D.current=false;clearTimeout(switchTimer.current);setSwitching3D(false);
  }
  function applyPending3D(){
    if(!pending3D.current || !map.current || map.current.getRenderingType()!==google.maps.RenderingType.VECTOR)return;
    // Rendering upgrades are asynchronous. The first idle may still be raster;
    // wait for VECTOR instead of consuming a one-shot idle listener too early.
    cancel3DSwitch();setViewMessage('');perspectiveRef.current=true;
    map.current.moveCamera({zoom:Math.max(17,map.current.getZoom()||2),tilt:50,heading:0});
  }
  function chooseView(tilted:boolean) {
    if(!map.current)return;
    cancel3DSwitch();setViewMessage('');
    if(!tilted){perspectiveRef.current=false;setPerspective(false);map.current.moveCamera({tilt:0,heading:0});return;}
    setSatellite(false);map.current.setMapTypeId('roadmap');
    pending3D.current=true;setSwitching3D(true);
    switchTimer.current=setTimeout(()=>{
      if(!pending3D.current)return;
      applyPending3D();
      if(!pending3D.current)return;
      cancel3DSwitch();setPerspective(false);perspectiveRef.current=false;
      const canvas=document.createElement('canvas'),gl=canvas.getContext('webgl2');
      const accelerated=!!gl;gl?.getExtension('WEBGL_lose_context')?.loseContext();
      setViewMessage(accelerated
        ? 'Google kept this map in 2D. Reload the page and retry 3D; browser or graphics-driver restrictions can prevent vector rendering.'
        : 'Chrome cannot create a WebGL 2 context. Enable graphics acceleration in Chrome Settings → System, relaunch Chrome, then retry 3D.');
    },8000);
    applyPending3D();
    if(pending3D.current){
      try{map.current.setRenderingType(google.maps.RenderingType.VECTOR);}
      catch{ /* Keep waiting for renderer events; the timeout gives recovery guidance. */ }
    }
  }
  function toggleSatellite() {cancel3DSwitch();setViewMessage('');setSatellite(!satellite); map.current?.setMapTypeId(satellite ? 'roadmap' : 'hybrid');}
  return <section className="google-map-area" aria-label="Geographic journey map">
    <div ref={host} className="google-map-host" aria-label="Journey map"/>
    {ready && <>
      <div className="journey-map-toolbar">
        <div className="journey-map-location"><span className="signal-dot"/><span>{active?'Your journey':chosenLocations?.origin||chosenLocations?.destination?'Selected locations':'Explore the map'}<small>{satellite ? 'Satellite + streets' : 'Street map'}</small></span></div>
        <div className="journey-map-switches">
          <button type="button" aria-label="Show 2D map" aria-pressed={!perspective} onClick={()=>chooseView(false)}>2D</button>
          <button type="button" aria-label="Show 3D map" aria-pressed={perspective} aria-busy={switching3D} disabled={switching3D} onClick={()=>chooseView(true)}>{switching3D?'Loading 3D…':'3D'}</button>
          <button type="button" aria-label="Toggle satellite imagery" aria-pressed={satellite} onClick={toggleSatellite}><Layers size={15}/><span>Satellite</span></button>
        </div>
      </div>
      {routes.length>0&&<nav className="journey-map-legend" aria-label="Route colors">{routes.map((route,index)=><button key={route.route_id} type="button" aria-label={`Show route ${index+1}`} aria-pressed={route.route_id===active?.route_id} onClick={()=>onSelect(route.route_id)}><span style={{background:routeColor(index)}} aria-hidden="true"/>Route {index+1}{route.route_id===active?.route_id&&<span className="route-legend-selected">Selected</span>}</button>)}</nav>}
      <div className="journey-map-tools" aria-label="Map camera controls">
        <button aria-label="Zoom map in" onClick={() => map.current?.setZoom(Math.min(21, (map.current.getZoom() || 15) + 1))}><Plus size={19}/></button>
        <button aria-label="Zoom map out" onClick={() => map.current?.setZoom(Math.max(3, (map.current.getZoom() || 15) - 1))}><Minus size={19}/></button>
        <button aria-label="Rotate map" disabled={!vector} onClick={()=>map.current?.setHeading(((map.current.getHeading()||0)+45)%360)}><RotateCcw size={19}/></button>
        <button aria-label="Point map north" onClick={() => map.current?.setHeading(0)}><Compass size={18}/></button>
        <button aria-label="Fit journey on map" onClick={fitJourney}><LocateFixed size={18}/></button>
      </div>
      {onChooseLocation && <div className="journey-map-picking"><button disabled={locating} aria-label="Use my location as start" onClick={useMyLocation}><LocateFixed size={14}/>{locating?'Locating…':'My location'}</button>{(['origin','destination'] as const).map(kind => <button key={kind} aria-pressed={picking === kind} onClick={() => setPicking(picking === kind ? null : kind)}><Crosshair size={14}/>{kind === 'origin' ? 'Choose start' : 'Choose destination'}</button>)}</div>}
      {picking && <p className="journey-map-hint" role="status">Click the map to choose your {picking === 'origin' ? 'start' : 'destination'}. <button onClick={() => setPicking(null)}>Cancel</button></p>}
      {viewMessage&&<p className="journey-map-hint" role="status">{viewMessage}<button onClick={()=>setViewMessage('')}>Dismiss</button></p>}
      {locationError&&<p className="journey-map-hint" role="status">{locationError}<button onClick={()=>setLocationError('')}>Dismiss</button></p>}
      {pinDetail && <div className="journey-pin-detail"><strong>{pinDetail.label}</strong><span>{Math.abs(pinDetail.position.lat).toFixed(5)}° {pinDetail.position.lat>=0?'N':'S'} · {Math.abs(pinDetail.position.lng).toFixed(5)}° {pinDetail.position.lng>=0?'E':'W'}</span><button onClick={() => setPinDetail(null)} aria-label="Close location details">×</button></div>}
      <div className="journey-map-provenance"><span>{active ? (live ? 'Returned road route' : 'Historical road route') : 'Choose a journey'}</span><small>{vector===null?'Preparing map views…':perspective?'3D perspective · building detail depends on coverage':'2D map · streets and satellite'}</small></div>
    </>}
    {!ready && <div className="map-setup" role="status"><Compass size={28}/><strong>{error ? 'Connect your map' : 'Opening your map'}</strong><p>{error || 'Loading Google streets and satellite imagery…'}</p>{error && mapsKey && <button onClick={() => setAttempt(value => value + 1)}><RotateCcw size={15}/>Retry map</button>}</div>}
  </section>;
}
