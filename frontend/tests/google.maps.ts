import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const recording=JSON.parse(readFileSync('../examples/delhi-recorded-response.json','utf8')).response;
// Entire Maps SDK is mocked here. The separate verify-map script loads real tiles.
const sdk=`
window.mapEvidence={paths:[],fits:0,pins:[],cameras:[],options:null};
class MockMap {constructor(el,options){this.el=el;this.options=options;this.listeners={};el.dataset.ready='true';window.mapEvidence.options=options;window.mapEvidence.map=this;this.pane=document.createElement('div');el.append(this.pane)} addListener(name,callback){(this.listeners[name]||=[]).push(callback);return{remove:()=>{this.listeners[name]=this.listeners[name].filter(c=>c!==callback)}}}fire(name,value){(this.listeners[name]||[]).forEach(fn=>fn(value))}fitBounds(){window.mapEvidence.fits++;this.fire('idle')}moveCamera(o){window.mapEvidence.cameras.push(o);if(o.tilt!==undefined){this.tilt=o.tilt;this.fire('tilt_changed')}}getRenderingType(){return this.rendering||'VECTOR'}getTilt(){return this.tilt||0}getHeading(){return window.mapEvidence.heading||0}setRenderingType(t){this.rendering=t;this.fire('renderingtype_changed');this.fire('idle')}setMapTypeId(id){window.mapEvidence.mapType=id}getZoom(){return 15}setZoom(z){window.mapEvidence.zoom=z}setHeading(h){window.mapEvidence.heading=h}}
class OverlayView {setMap(map){if(this.map)this.onRemove();this.map=map;if(map){this.onAdd();this.draw()}}getPanes(){return{overlayMouseTarget:this.map.pane}}getProjection(){return{fromLatLngToDivPixel:p=>{window.mapEvidence.pins.push(p.value);return{x:180+(p.value.lng-77.2)*800,y:180+(p.value.lat-28.6)*800}}}}static preventMapHitsAndGesturesFrom(){}}
window.google={maps:{Map:MockMap,OverlayView,RenderingType:{VECTOR:'VECTOR',RASTER:'RASTER'},LatLng:class{constructor(value){this.value=value}},LatLngBounds:class{extend(){}},Polyline:class{constructor(o){this.options=o;window.mapEvidence.paths.push(o.path);(window.mapEvidence.lines||=[]).push(this)}addListener(){return{remove(){}}}setOptions(o){Object.assign(this.options,o)}setMap(map){this.options.map=map}},event:{clearInstanceListeners(){},addListenerOnce(map,name,fn){map.addListener(name,fn)}}}};
window.ecoGoogleReady();`;
async function mockMap(page:Page){await page.route('https://maps.googleapis.com/**',route=>route.fulfill({contentType:'application/javascript',body:sdk}));}

test('Air quality empty state explains how to choose a route instead of showing dashes',async({page})=>{
 await mockMap(page);await page.goto('/');await page.getByRole('button',{name:'Air quality',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Choose a route first'})).toBeVisible();
 await expect(page.locator('.air-quality-reading')).toHaveCount(0);
 await expect(page.getByText('Source-dependent',{exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Choose a route',exact:true}).click();
 await expect(page.getByLabel('Origin',{exact:true})).toBeVisible();
});

test('guest route data check works without requesting the protected dataset endpoint and clears on selection',async({page})=>{
 await mockMap(page);let qualityRequests=0;
 await page.route('**/api/v1/data/quality',r=>{qualityRequests++;return r.fulfill({status:401,json:{}});});
 await page.route('**/api/v1/routes/preview',r=>r.fulfill({json:{...recording,persistence:'request_only'}}));
 await page.goto('/');await page.getByLabel('Origin',{exact:true}).fill('India Gate, New Delhi');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place, New Delhi');
 await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Compare routes',exact:true}).click();await expect(page.locator('.route-option')).toHaveCount(2);
 for(const size of [{width:1280,height:720},{width:390,height:844}]){
  await page.setViewportSize(size);await page.getByRole('button',{name:'Air quality',exact:true}).click();
  await expect(page.locator('.air-quality-reading')).toContainText('69.2');
  await expect(page.getByText('Whole journey',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Check route data',exact:true}).click();
  await expect(page.locator('.air-quality-check')).toContainText('match the route’s exposure estimate');
  await expect(page.locator('.air-quality-check')).toContainText('does not fetch new readings');
  await expect.poll(()=>page.locator('.air-quality-check').evaluate(el=>{
   const box=el.getBoundingClientRect(),panel=el.closest('.detail-panel')!.getBoundingClientRect();
   return box.top>=panel.top&&box.bottom<=panel.bottom+1;
  })).toBe(true);
  expect(await page.locator('.air-quality-content').evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
  await page.screenshot({path:`../work/air-quality-simple-${size.width}.png`});
 }
 expect(qualityRequests).toBe(0);
 await page.getByRole('button',{name:'Journeys',exact:true}).click();await page.locator('.route-option').nth(1).click();
 await page.getByRole('button',{name:'Air quality',exact:true}).click();await expect(page.locator('.air-quality-check')).toHaveCount(0);
 await page.getByRole('button',{name:'Check route data',exact:true}).click();await expect(page.locator('.air-quality-check')).toContainText('match the route’s exposure estimate');
});

test('missing route pollution is clearly unavailable and the data check does not claim success',async({page})=>{
 await mockMap(page);const data=structuredClone(recording);
 for(const route of data.routes){route.estimated_pm25_exposure_ug_h_m3=null;route.pm25_coverage_fraction=0;route.segments=[];route.source_metadata=[];}
 await page.route('**/api/v1/routes/preview',r=>r.fulfill({json:{...data,persistence:'request_only'}}));
 await page.goto('/');await page.getByLabel('Origin',{exact:true}).fill('Gateway of India, Mumbai');await page.getByLabel('Destination',{exact:true}).fill('Marine Drive, Mumbai');
 await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Compare routes',exact:true}).click();await expect(page.locator('.route-option')).toHaveCount(2);
 await page.getByRole('button',{name:'Air quality',exact:true}).click();await expect(page.getByRole('heading',{name:'Air estimate unavailable'})).toBeVisible();
 await expect(page.locator('.air-quality-content')).toContainText('Missing data does not mean clean air');await expect(page.locator('.air-quality-reading')).toHaveCount(0);
 await page.getByRole('button',{name:'Check route data',exact:true}).click();await expect(page.locator('.air-quality-check')).toContainText('0 of 0');
 await expect(page.locator('.air-quality-check')).toContainText('could not be verified');
});

test('signed-in dataset check renders a readable result and recovers from AWS failure without exposing provider text',async({page})=>{
 await mockMap(page);
 await page.addInitScript(()=>sessionStorage.setItem('ecoroute-pkce',JSON.stringify({verifier:'test-verifier',state:'test-state',created:Date.now()})));
 await page.route('**/oauth2/token',r=>r.fulfill({json:{access_token:'test-only-token',expires_in:3600}}));
 await page.route('**/api/v1/routes/compare',r=>r.fulfill({json:recording}));
 let qualityCalls=0;
 await page.route('**/api/v1/data/quality',r=>{qualityCalls++;expect(r.request().headers().authorization).toBe('Bearer test-only-token');return qualityCalls===1?r.fulfill({status:503,json:{error:{code:'storage_unavailable',message:'PRIVATE_PROVIDER_DETAIL'}}}):r.fulfill({json:{status:'available',reports:[{records:192,missing_or_rejected:0,flagged:0,raw_key:'PRIVATE_PATH'}],truncated:false}});});
 await page.goto('/?code=test-code&state=test-state');await expect(page.locator('.notice')).toContainText('Signed in');
 await page.getByLabel('Origin',{exact:true}).fill('India Gate, New Delhi');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place, New Delhi');
 await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Compare routes',exact:true}).click();await expect(page.locator('.route-option')).toHaveCount(2);
 await page.getByRole('button',{name:'Air quality',exact:true}).click();await page.getByText('About this estimate',{exact:true}).click();
 await page.getByRole('button',{name:'Check collected datasets',exact:true}).click();await expect(page.locator('.air-quality-error')).toBeVisible();
 await expect(page.locator('.air-quality-content')).not.toContainText('PRIVATE_PROVIDER_DETAIL');
 await page.getByRole('button',{name:'Check collected datasets',exact:true}).click();await expect(page.locator('.air-quality-content')).toContainText('192 readings');
 await expect(page.locator('.air-quality-error')).toHaveCount(0);await expect(page.locator('.air-quality-content')).not.toContainText('PRIVATE_PATH');
 expect(qualityCalls).toBe(2);
});

test('request-only Insights invokes backend explanation and reports its real mode',async({page})=>{
 await page.setViewportSize({width:1280,height:720});await mockMap(page);const bodies:any[]=[];
 await page.route('**/api/v1/routes/preview',route=>{const body=route.request().postDataJSON();bodies.push(body);return route.fulfill({json:{...recording,persistence:'request_only',...(body.include_explanation?{explanation:{explanation:'Verified server-calculated explanation. '.repeat(25),mode:'gemini_arranged_approved_text',fallback_reason:null}}:{})}});});
 await page.goto('/');await page.getByLabel('Origin',{exact:true}).fill('Gateway of India, Mumbai');await page.getByLabel('Destination',{exact:true}).fill('Marine Drive, Mumbai');
 await page.getByRole('checkbox',{name:'Allow processing my locations and route. Google routes are not saved.'}).check();
 await page.getByRole('button',{name:'Compare routes',exact:true}).click();await expect(page.locator('.route-option')).toHaveCount(2);
 await page.getByRole('button',{name:'Insights',exact:true}).click();await page.getByRole('button',{name:'Explain this comparison'}).click();
 await expect(page.locator('.explanation')).toContainText('Verified server-calculated explanation');
 await expect(page.locator('.explanation')).toContainText('Explained with Gemini · based on your route results');
 const badge=await page.locator('.explanation small').boundingBox();const panel=await page.locator('.detail-panel').boundingBox();
 expect(badge).not.toBeNull();expect(panel).not.toBeNull();expect(badge!.y).toBeGreaterThanOrEqual(panel!.y);expect(badge!.y+badge!.height).toBeLessThanOrEqual(Math.min(720,panel!.y+panel!.height));
 expect(bodies).toHaveLength(2);expect(bodies[1].include_explanation).toBe(true);expect(bodies[1].consent_to_store).toBe(false);
 expect(bodies[1].routes).toBeUndefined();expect(bodies[1].estimated_pm25_exposure_ug_h_m3).toBeUndefined();
});

test('route factor controls stay inside the planner and send compatible guest preferences',async({page})=>{
 await page.setViewportSize({width:1366,height:768});await mockMap(page);
 let submitted:any;
 await page.route('**/api/v1/routes/preview',route=>{submitted=route.request().postDataJSON();return route.fulfill({json:{...recording,persistence:'request_only'}});});
 await page.goto('/');await page.getByText('Route factors & forecasts',{exact:true}).click();
 await expect(page.getByRole('button',{name:'Check station forecast availability'})).toBeDisabled();
 const body=await page.locator('.route-preferences-body').boundingBox();
 const planner=await page.locator('.detail-panel').boundingBox();
 expect(body).not.toBeNull();expect(planner).not.toBeNull();
 expect(body!.y).toBeGreaterThanOrEqual(planner!.y);expect(body!.x).toBeGreaterThanOrEqual(planner!.x);
 expect(body!.x+body!.width).toBeLessThanOrEqual(planner!.x+planner!.width);
 await page.getByLabel('Weather preference',{exact:true}).focus();await page.keyboard.press('End');
 await page.getByRole('checkbox',{name:'Prefer avoiding tolls'}).check();
 await page.screenshot({path:'../work/route-factor-controls-desktop.png'});
 await page.getByText('Route factors & forecasts',{exact:true}).click();
 await page.getByLabel('Origin',{exact:true}).fill('India Gate, New Delhi');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place, New Delhi');
 await page.getByRole('checkbox',{name:'Allow processing my locations and route. Google routes are not saved.'}).check();
 await page.getByRole('button',{name:'Compare routes',exact:true}).click();
 await expect(page.locator('.route-option')).toHaveCount(2);
 expect(submitted.weather_weight).toBe(.2);expect(submitted.avoid_tolls).toBe(true);
 expect(submitted.terrain_weight).toBe(0);expect(submitted.station_ids).toBeUndefined();
 expect(submitted.consent_to_store).toBe(false);
});

test('map is public, tilted, controllable, and does not invent initial journey pins',async({page})=>{
 await mockMap(page);await page.goto('/');
 await expect(page.getByLabel('Journey map',{exact:true})).toHaveAttribute('data-ready','true');
 await expect(page.locator('.journey-pin')).toHaveCount(0);
 await expect(page.locator('.route-option')).toHaveCount(0);
 const result=await page.evaluate(()=> (window as any).mapEvidence.options);
 expect(result.mapTypeId).toBe('roadmap');await expect(page.getByLabel('Toggle satellite imagery')).toHaveAttribute('aria-pressed','false');expect(result.renderingType).toBe('VECTOR');expect(result.tilt).toBe(0);expect(result.center).toEqual({lat:0,lng:0});
 await expect(page.getByLabel('Origin',{exact:true})).toHaveValue('');await expect(page.getByLabel('Destination',{exact:true})).toHaveValue('');
 await page.getByLabel('Show 3D map').click();
 expect(await page.evaluate(()=> (window as any).mapEvidence.cameras.at(-1).tilt)).toBe(50);
 await page.getByLabel('Toggle satellite imagery').click();
 expect(await page.evaluate(()=> (window as any).mapEvidence.mapType)).toBe('hybrid');
});

for(const [label,mode] of [['Drive','driving'],['Walk','walking'],['Cycle','cycling']]){
 test(`${label} submits an unauthenticated request-only comparison and draws provider route pins`,async({page})=>{
  await mockMap(page);
  let sent:any;
  await page.route('**/api/v1/routes/preview',route=>{
   sent=route.request().postDataJSON();expect(route.request().headers().authorization).toBeUndefined();
   const response=structuredClone(recording);response.persistence='request_only';
   if(sent.include_explanation)response.explanation={explanation:'Server deterministic fixture summary',mode:'deterministic',fallback_reason:'bedrock_disabled'};
   for(const r of response.routes)r.routing_source={provider:mode==='cycling'?'openrouteservice':'google_routes',fixture:true};
   return route.fulfill({json:response});
  });
  await page.goto('/');await page.getByRole('button',{name:label,exact:true}).click();
  await page.getByLabel('Origin',{exact:true}).fill('28.612900, 77.229500');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place, New Delhi');
  await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Compare routes',exact:true}).click();
  await expect(page.locator('.route-option')).toHaveCount(2);
  expect(sent.mode).toBe(mode);expect(sent.consent_to_store).toBe(false);expect(sent.origin).toEqual({latitude:28.6129,longitude:77.2295});
  await expect(page.locator('.journey-pin')).toHaveCount(2);
  const paths=await page.evaluate(()=> (window as any).mapEvidence.paths);
  expect(paths[0].length).toBeGreaterThan(10);expect(paths[0][0].lat).toBeGreaterThan(28);expect(paths[0][0].lng).toBeGreaterThan(77);
  await page.getByRole('button',{name:'Alternative route'}).click();
  await expect(page.locator('.route-option.chosen')).toContainText('Alternative route');
  await page.getByRole('button',{name:'Insights',exact:true}).click();await page.getByRole('button',{name:'Explain this comparison'}).click();
  await expect(page.getByText('Route summary · based on your route results',{exact:true})).toBeVisible();
 });
}

test('map picks actual coordinates, pins are projected and route mode change clears stale results',async({page})=>{
 await mockMap(page);await page.goto('/');
 await page.getByRole('button',{name:'Choose start',exact:true}).click();
 await page.evaluate(()=> (window as any).mapEvidence.map.fire('click',{latLng:{toJSON:()=>({lat:28.6129,lng:77.2295})}}));
 await expect(page.getByLabel('Origin',{exact:true})).toHaveValue('28.612900, 77.229500');
 await expect(page.locator('.journey-pin-origin')).toHaveCount(1);
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await expect(page.getByRole('button',{name:'Choose destination',exact:true})).toBeVisible();
});

test('missing cycling credentials show a specific error without exposing provider text',async({page})=>{
 await mockMap(page);await page.route('**/api/v1/routes/preview',route=>route.fulfill({status:503,json:{error:{code:'cycling_key_missing',message:'PRIVATE_PROVIDER_SECRET'}}}));
 await page.goto('/');await page.getByRole('button',{name:'Cycle',exact:true}).click();await page.getByLabel('Origin',{exact:true}).fill('India Gate, New Delhi');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place, New Delhi');await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Compare routes',exact:true}).click();
 await expect(page.getByText('Add OPENROUTESERVICE_API_KEY',{exact:false})).toBeVisible();await expect(page.getByText('PRIVATE_PROVIDER_SECRET')).toHaveCount(0);await expect(page.locator('.route-option')).toHaveCount(0);
});

test('Google map load failure leaves planner and retry usable',async({page})=>{
 await page.route('https://maps.googleapis.com/**',route=>route.abort());await page.goto('/');
 await expect(page.getByText('Google Maps could not load.',{exact:false})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Your next journey'})).toBeVisible();await expect(page.getByRole('button',{name:'Retry map'})).toBeVisible();
});


test('location fields have no red outline and geolocation is requested only by its button',async({page,context})=>{
 await context.grantPermissions(['geolocation']);await context.setGeolocation({latitude:19.076,longitude:72.8777});
 await mockMap(page);await page.goto('/');
 await page.getByLabel('Origin',{exact:true}).click();
 expect(await page.getByLabel('Origin',{exact:true}).evaluate(el=>getComputedStyle(el).outlineStyle)).toBe('none');
 await page.getByRole('button',{name:'Use my location as start'}).click();
 await expect(page.getByLabel('Origin',{exact:true})).toHaveValue('19.076000, 72.877700');
 await expect(page.locator('.journey-pin-origin')).toHaveCount(1);
 await expect(page.getByLabel('Destination',{exact:true})).toHaveValue('');
});


test('3D zooms into street geometry, rotates, and switches back to overhead 2D',async({page})=>{
 await mockMap(page);await page.goto('/');await page.getByLabel('Show 3D map').click();
 const camera=await page.evaluate(()=> (window as any).mapEvidence.cameras.at(-1));
 expect(camera.zoom).toBeGreaterThanOrEqual(17);expect(camera.tilt).toBe(50);
 await expect(page.getByLabel('Show 3D map')).toHaveAttribute('aria-pressed','true');
 expect(await page.evaluate(()=> (window as any).mapEvidence.mapType)).toBe('roadmap');
 await page.getByLabel('Rotate map',{exact:true}).click();
 expect(await page.evaluate(()=> (window as any).mapEvidence.heading)).toBe(45);
 await page.getByLabel('Show 2D map').click();
 expect(await page.evaluate(()=> (window as any).mapEvidence.cameras.at(-1).tilt)).toBe(0);
 await expect(page.getByLabel('Show 2D map')).toHaveAttribute('aria-pressed','true');
});
test('unknown initialization does not permanently disable 3D and late vector readiness is detected',async({page})=>{
 await page.route('https://maps.googleapis.com/**',route=>route.fulfill({contentType:'application/javascript',body:sdk.replace("return this.rendering||'VECTOR'","return this.rendering||'UNINITIALIZED'")}));
 await page.goto('/');await expect(page.locator('.journey-map-provenance')).toContainText('Preparing map views');
 await page.evaluate(()=>{const m=(window as any).mapEvidence.map;m.rendering='VECTOR';m.fire('tilesloaded');});
 await expect(page.locator('.journey-map-provenance')).toContainText('2D map');
 await page.getByLabel('Show 3D map').click();await expect(page.getByLabel('Show 3D map')).toHaveAttribute('aria-pressed','true');
});
test('persistent raster fallback preserves 2D and explains recovery without claiming active 3D',async({page})=>{
 await page.route('https://maps.googleapis.com/**',route=>route.fulfill({contentType:'application/javascript',body:sdk.replace("return this.rendering||'VECTOR'","return 'RASTER'")}));
 await page.goto('/');await expect(page.getByLabel('Show 2D map')).toBeEnabled();
 await page.getByLabel('Show 3D map').click();
 await expect(page.getByRole('status')).toContainText(/Google kept this map in 2D|Chrome cannot create a WebGL 2 context/,{timeout:12000});
 await expect(page.getByLabel('Show 3D map')).toHaveAttribute('aria-pressed','false');
 await page.getByLabel('Toggle satellite imagery').click();
 await page.getByLabel('Zoom map in').click();
 expect(await page.evaluate(()=> (window as any).mapEvidence.zoom)).toBe(16);
});

test('3D waits through an early raster idle and applies tilt when vector becomes ready',async({page})=>{
 const delayed=sdk.replace("return this.rendering||'VECTOR'","return this.rendering||'RASTER'").replace("setRenderingType(t){this.rendering=t;this.fire('renderingtype_changed');this.fire('idle')}","setRenderingType(t){this.fire('idle');setTimeout(()=>{this.rendering=t;this.fire('renderingtype_changed');this.fire('idle')},500)}");
 await page.route('https://maps.googleapis.com/**',route=>route.fulfill({contentType:'application/javascript',body:delayed}));
 await page.goto('/');await page.getByLabel('Show 3D map').click();
 await expect(page.getByLabel('Show 3D map')).toHaveAttribute('aria-busy','true');
 await expect(page.getByLabel('Show 3D map')).toHaveAttribute('aria-pressed','true');
 await expect(page.getByLabel('Show 3D map')).toHaveAttribute('aria-busy','false');
 await expect(page.locator('.journey-map-hint')).toHaveCount(0);
 expect(await page.evaluate(()=> (window as any).mapEvidence.cameras.at(-1).tilt)).toBe(50);
});
test('choosing 2D cancels a pending renderer upgrade and never tilts later',async({page})=>{
 const delayed=sdk.replace("return this.rendering||'VECTOR'","return this.rendering||'RASTER'").replace("setRenderingType(t){this.rendering=t;this.fire('renderingtype_changed');this.fire('idle')}","setRenderingType(t){this.fire('idle');setTimeout(()=>{this.rendering=t;this.fire('renderingtype_changed');this.fire('idle')},500)}");
 await page.route('https://maps.googleapis.com/**',route=>route.fulfill({contentType:'application/javascript',body:delayed}));
 await page.goto('/');await page.getByLabel('Show 3D map').click();await page.getByLabel('Show 2D map').click();
 await page.waitForTimeout(700);
 await expect(page.getByLabel('Show 2D map')).toHaveAttribute('aria-pressed','true');
 expect(await page.evaluate(()=> (window as any).mapEvidence.cameras.at(-1).tilt)).toBe(0);
 await expect(page.locator('.journey-map-hint')).toHaveCount(0);
});

test('alternative colors match cards and map legend, persist across selection, and keep genuine geometry',async({page})=>{
 await mockMap(page);await page.route('**/api/v1/routes/preview',route=>route.fulfill({json:recording}));
 await page.goto('/');await page.getByLabel('Origin',{exact:true}).fill('India Gate');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place');
 await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Compare routes',exact:true}).click();
 await expect(page.getByLabel('Route colors')).toBeVisible();
 const lines=()=>page.evaluate(()=> (window as any).mapEvidence.lines.filter((l:any)=>l.options.map&&l.options.strokeColor!=='#ffffff').map((l:any)=>({color:l.options.strokeColor,width:l.options.strokeWeight,path:l.options.path})));
 const initial=await lines();expect(initial).toHaveLength(2);expect(initial[0].color).not.toBe(initial[1].color);
 expect(initial[0].path[0]).toEqual({lat:recording.routes[0].geometry.coordinates[0][1],lng:recording.routes[0].geometry.coordinates[0][0]});
 const color=await page.locator('.route-option').nth(1).locator('.route-dot').evaluate(el=>getComputedStyle(el).backgroundColor);
 const legend=await page.getByLabel('Show route 2',{exact:true}).locator('span').first().evaluate(el=>getComputedStyle(el).backgroundColor);expect(color).toBe(legend);
 await page.getByLabel('Show route 2',{exact:true}).click();
 await expect(page.getByLabel('Show route 2',{exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('.selected-route-context')).toContainText('Route 2 selected');
 const changed=await lines();expect(changed.map((l:any)=>l.color)).toEqual(initial.map((l:any)=>l.color));
 expect(changed[1].width).toBeGreaterThan(changed[0].width);
 expect(changed.map((l:any)=>l.path)).toEqual(initial.map((l:any)=>l.path));
 await page.screenshot({path:'../work/route-colors-fixed.png'});
});

test('pure objectives disable unused sliders and restore balanced priorities',async({page})=>{
 await mockMap(page);await page.goto('/');
 await page.getByText('Route factors & forecasts',{exact:true}).click();
 await page.getByLabel('Weather preference',{exact:true}).focus();await page.keyboard.press('End');
 await page.getByLabel('Route preference',{exact:true}).selectOption('fastest');
 await expect(page.getByLabel('Pollution priority',{exact:true})).toBeDisabled();
 await expect(page.getByLabel('Weather preference',{exact:true})).toBeDisabled();
 await expect(page.getByRole('checkbox',{name:'Prefer avoiding tolls'})).toBeEnabled();
 await page.getByLabel('Route preference',{exact:true}).selectOption('lowest_exposure');
 await expect(page.getByLabel('Pollution priority',{exact:true})).toBeDisabled();
 await page.getByLabel('Route preference',{exact:true}).selectOption('balanced');
 await expect(page.getByLabel('Weather preference',{exact:true})).toBeEnabled();
 await expect(page.getByLabel('Weather preference',{exact:true})).toHaveValue('20');
});

test('city overview submits objectives and detour, then warns until changed settings are recomputed',async({page})=>{
 await mockMap(page);let sent:any;
 await page.route('**/api/v1/routes/preview',r=>{
  sent=r.request().postDataJSON();const response=structuredClone(recording);response.persistence='request_only';
  response.selected_route_id=response.routes[sent.objective==='lowest_exposure'&&sent.max_detour_percent>0?1:0].route_id;
  if(sent.max_detour_percent===0){response.routes[1].within_detour_limit=false;response.routes[1].detour_percent=15;}
  return r.fulfill({json:response});
 });
 await page.goto('/');await page.getByLabel('Origin',{exact:true}).fill('India Gate, New Delhi');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place, New Delhi');
 await page.getByRole('checkbox',{name:'Allow processing my locations and route. Google routes are not saved.'}).check();
 await page.getByRole('button',{name:'Compare routes',exact:true}).click();await expect(page.locator('.route-option')).toHaveCount(2);
 await expect(page.getByText('Settings changed. Compare again to update these routes.')).toHaveCount(0);
 await page.getByLabel('Route preference',{exact:true}).selectOption('lowest_exposure');
 await page.getByLabel('Maximum detour',{exact:true}).selectOption('0');
 await expect(page.getByText('Settings changed. Compare again to update these routes.')).toBeVisible();
 await page.getByRole('button',{name:'Compare routes',exact:true}).click();
 await expect(page.getByText('Settings changed. Compare again to update these routes.')).toHaveCount(0);
 expect(sent.objective).toBe('lowest_exposure');expect(sent.exposure_weight).toBe(1);expect(sent.weather_weight).toBe(0);expect(sent.max_detour_percent).toBe(0);
 await expect(page.locator('.route-detour-warning')).toContainText('Outside detour limit');
 await expect(page.locator('.selected-route-context')).toContainText('Route 1 selected'); // UI honors response; ranking arithmetic is tested in Python.
});

test('departure defaults to a fresh leave-now value and scheduled dates reach the backend',async({page})=>{
 await mockMap(page);let sent:any;
 await page.route('**/api/v1/routes/preview',r=>{sent=r.request().postDataJSON();return r.fulfill({json:recording});});
 await page.goto('/');await expect(page.getByLabel('Departure timing',{exact:true})).toHaveValue('now');
 await expect(page.getByLabel('Departure',{exact:true})).toHaveCount(0);
 await page.getByLabel('Origin',{exact:true}).fill('India Gate, New Delhi');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place, New Delhi');
 await page.getByRole('checkbox',{name:'Allow processing my locations and route. Google routes are not saved.'}).check();
 await page.getByRole('button',{name:'Compare routes',exact:true}).click();await expect(page.locator('.route-option')).toHaveCount(2);
 const now=await page.evaluate(()=>Date.now());expect(new Date(sent.departure_at).getTime()-now).toBeGreaterThan(0);expect(new Date(sent.departure_at).getTime()-now).toBeLessThan(65000);
 await page.getByLabel('Departure timing',{exact:true}).selectOption('planned');
 const plan=await page.evaluate(()=>{const date=new Date(Date.now()+3600000);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);});
 await page.getByLabel('Departure',{exact:true}).fill(plan);
 const expected=await page.evaluate(v=>new Date(v).toISOString(),plan);
 await page.getByRole('button',{name:'Compare routes',exact:true}).click();await expect(page.locator('.route-option')).toHaveCount(2);
 await expect.poll(()=>sent.departure_at).toBe(expected);
});

test('planner keeps consent gating and replaces red click outlines with keyboard-visible neutral focus',async({page})=>{
 await mockMap(page);let requests=0;
 await page.route('**/api/v1/routes/preview',r=>{requests++;return r.fulfill({json:recording});});
 await page.goto('/');
 const city=page.getByRole('button',{name:'City overview',exact:true});await city.click();
 expect(await city.evaluate(el=>getComputedStyle(el).outlineStyle)).toBe('none');
 const checkbox=page.getByRole('checkbox',{name:'Allow processing my locations and route. Google routes are not saved.'});
 await expect(checkbox).toBeVisible();await expect(checkbox).not.toBeChecked();
 await page.getByLabel('Origin',{exact:true}).fill('India Gate, New Delhi');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place, New Delhi');
 await page.getByRole('button',{name:'Compare routes',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('Confirm location processing');expect(requests).toBe(0);
 const preference=page.getByLabel('Route preference',{exact:true});
 await preference.click();await page.keyboard.press('Home');await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
 await expect(preference).toHaveValue('fastest');
 const focus=await preference.evaluate(el=>({color:getComputedStyle(el).outlineColor,width:getComputedStyle(el).outlineWidth}));
 expect(focus.color).toBe('rgb(54, 84, 101)');expect(focus.width).toBe('2px');
 await checkbox.check();await page.getByRole('button',{name:'Compare routes',exact:true}).click();
 await expect(page.locator('.route-option')).toHaveCount(2);expect(requests).toBe(1);
});

for(const viewport of [{width:1280,height:720},{width:1024,height:640}]){
 test(`compare action remains fully inside the planner at ${viewport.width}x${viewport.height}`,async({page})=>{
  await page.setViewportSize(viewport);await mockMap(page);await page.goto('/');await page.evaluate(()=>document.fonts.ready);
  const button=await page.getByRole('button',{name:'Compare routes',exact:true}).boundingBox(),panel=await page.locator('.detail-panel').boundingBox();
  expect(button!.y+button!.height).toBeLessThanOrEqual(panel!.y+panel!.height-5);
  await expect(page.getByRole('checkbox',{name:'Allow processing my locations and route. Google routes are not saved.'})).toBeVisible();
 });
}
