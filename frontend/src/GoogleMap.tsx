/// <reference types="google.maps" />
import {useEffect, useRef, useState} from 'react';
import {Compass, Crosshair, Layers, LocateFixed, Minus, Plus, RotateCcw} from 'lucide-react';
import type {Route} from './data';
import {routePath} from './mapGeometry';
import './journey-map.css';

export const mapsKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
const mapId = import.meta.env.VITE_GOOGLE_MAP_ID || '';
const DELHI = {lat:28.6139, lng:77.209};
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
  originLabel='India Gate', destinationLabel='Connaught Place', chosenLocations, onChooseLocation}:Props) {
  const host = useRef<HTMLDivElement>(null), map = useRef<google.maps.Map|null>(null);
  const lines = useRef<{route:Route; line:google.maps.Polyline}[]>([]), fitted = useRef('');
  const perspectiveRef = useRef(true);
  const [ready, setReady] = useState(false), [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0), [perspective, setPerspective] = useState(true);
  const [vector, setVector] = useState(true), [satellite, setSatellite] = useState(true);
  const [picking, setPicking] = useState<'origin'|'destination'|null>(null);
  const [pinDetail, setPinDetail] = useState<{label:string; position:google.maps.LatLngLiteral}|null>(null);
  const active = routes.find(route => route.route_id === selected && routePath(route).length >= 2)
    || routes.find(route => routePath(route).length >= 2);

  useEffect(() => {
    let mounted = true;
    setReady(false); setError(''); fitted.current = '';
    const authError = () => {setReady(false); setError('Google Maps could not authorize this website. Check Maps JavaScript API, billing and website restrictions.');};
    window.addEventListener('google-map-auth-error', authError);
    if (!mapsKey) {
      setError('Add VITE_GOOGLE_MAPS_API_KEY to frontend/.env.local and restart the development server.');
      return () => window.removeEventListener('google-map-auth-error', authError);
    }
    loadMaps().then(() => {
      if (!mounted || !host.current) return;
      map.current = new google.maps.Map(host.current, {
        center:DELHI, zoom:15.5, tilt:50, heading:0, renderingType:google.maps.RenderingType.VECTOR,
        ...(mapId ? {mapId} : {}), mapTypeId:'hybrid', mapTypeControl:false,
        streetViewControl:false, fullscreenControl:false, zoomControl:false, rotateControl:false,
        cameraControl:false, clickableIcons:true, tiltInteractionEnabled:true,
        headingInteractionEnabled:true, gestureHandling:'cooperative', isFractionalZoomEnabled:true,
      });
      setReady(true);
      google.maps.event.addListenerOnce(map.current, 'tilesloaded', () => {if (mounted && host.current) host.current.dataset.tilesLoaded='true';});
      map.current.addListener('renderingtype_changed', () => {
        if (!mounted || !map.current) return;
        const available = map.current.getRenderingType() === google.maps.RenderingType.VECTOR;
        setVector(available);
        if (!available) {setPerspective(false); perspectiveRef.current = false;}
      });
    }).catch(() => {if (mounted) setError('Google Maps could not load. Check your connection, key restrictions and billing, then retry.');});
    return () => {
      mounted = false;
      if (map.current) google.maps.event.clearInstanceListeners(map.current);
      map.current = null; host.current?.replaceChildren();
      window.removeEventListener('google-map-auth-error', authError);
    };
  }, [attempt]);

  useEffect(() => {
    if (!ready || !map.current) return;
    const overlays = routes.filter(route => routePath(route).length >= 2).map(route => {
      const line = new google.maps.Polyline({map:map.current, path:routePath(route), strokeColor:'#6d7d83', strokeOpacity:0.85, strokeWeight:5, zIndex:1});
      line.addListener('click', () => onSelect(route.route_id)); return {route, line};
    });
    lines.current = overlays;
    return () => {overlays.forEach(({line}) => {google.maps.event.clearInstanceListeners(line); line.setMap(null);}); lines.current = [];};
  }, [ready, routes, onSelect]);

  useEffect(() => {
    lines.current.forEach(({route, line}) => line.setOptions({
      strokeColor:route.route_id === active?.route_id ? '#f47732' : '#8fa4ac',
      strokeOpacity:route.route_id === active?.route_id ? 1 : 0.75,
      strokeWeight:route.route_id === active?.route_id ? 8 : 5,
      zIndex:route.route_id === active?.route_id ? 3 : 1,
    }));
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
    if (!points.length) {map.current.moveCamera({center:DELHI, zoom:15.5, tilt:perspectiveRef.current ? 50 : 0, heading:0}); return;}
    const bounds = new google.maps.LatLngBounds(); points.forEach(point => bounds.extend(point));
    // fitBounds resets tilt and heading; restore the requested view after it finishes.
    google.maps.event.addListenerOnce(map.current, 'idle', () => {map.current?.moveCamera({tilt:perspectiveRef.current ? 50 : 0, heading:0});});
    map.current.fitBounds(bounds, {top:96, bottom:70, left:65, right:65});
  }
  useEffect(() => {
    const signature = routes.map(route => route.route_id).join('|') || 'delhi';
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

  function togglePerspective() {const next = !perspective; setPerspective(next); perspectiveRef.current = next; map.current?.moveCamera({tilt:next ? 50 : 0, heading:0});}
  function toggleSatellite() {setSatellite(!satellite); map.current?.setMapTypeId(satellite ? 'roadmap' : 'hybrid');}
  return <section className="google-map-area" aria-label="Geographic journey map">
    <div ref={host} className="google-map-host" aria-label="Journey map"/>
    {ready && <>
      <div className="journey-map-toolbar">
        <div className="journey-map-location"><span className="signal-dot"/><span>New Delhi<small>{satellite ? 'Satellite + streets' : 'Street map'}</small></span></div>
        <div className="journey-map-switches">
          <button type="button" aria-label="Toggle tilted perspective" aria-pressed={perspective} disabled={!vector} onClick={togglePerspective}>{perspective ? '3D view' : '2D view'}</button>
          <button type="button" aria-label="Toggle satellite imagery" aria-pressed={satellite} onClick={toggleSatellite}><Layers size={15}/><span>Satellite</span></button>
        </div>
      </div>
      <div className="journey-map-tools" aria-label="Map camera controls">
        <button aria-label="Zoom map in" onClick={() => map.current?.setZoom(Math.min(21, (map.current.getZoom() || 15) + 1))}><Plus size={19}/></button>
        <button aria-label="Zoom map out" onClick={() => map.current?.setZoom(Math.max(3, (map.current.getZoom() || 15) - 1))}><Minus size={19}/></button>
        <button aria-label="Point map north" onClick={() => map.current?.setHeading(0)}><Compass size={18}/></button>
        <button aria-label="Fit journey on map" onClick={fitJourney}><LocateFixed size={18}/></button>
      </div>
      {onChooseLocation && <div className="journey-map-picking">{(['origin','destination'] as const).map(kind => <button key={kind} aria-pressed={picking === kind} onClick={() => setPicking(picking === kind ? null : kind)}><Crosshair size={14}/>{kind === 'origin' ? 'Choose start' : 'Choose destination'}</button>)}</div>}
      {picking && <p className="journey-map-hint" role="status">Click the map to choose your {picking === 'origin' ? 'start' : 'destination'}. <button onClick={() => setPicking(null)}>Cancel</button></p>}
      {pinDetail && <div className="journey-pin-detail"><strong>{pinDetail.label}</strong><span>{pinDetail.position.lat.toFixed(5)}° N · {pinDetail.position.lng.toFixed(5)}° E</span><button onClick={() => setPinDetail(null)} aria-label="Close location details">×</button></div>}
      <div className="journey-map-provenance"><span>{active ? (live ? 'Returned road route' : 'Historical road route') : 'Choose a journey'}</span><small>{vector ? 'Tilted view · building detail depends on coverage' : '2D map · 3D rendering unavailable on this device'}</small></div>
    </>}
    {!ready && <div className="map-setup" role="status"><Compass size={28}/><strong>{error ? 'Connect your map' : 'Opening New Delhi'}</strong><p>{error || 'Loading Google streets and satellite imagery…'}</p>{error && mapsKey && <button onClick={() => setAttempt(value => value + 1)}><RotateCcw size={15}/>Retry map</button>}</div>}
  </section>;
}
