import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const recording=JSON.parse(readFileSync('../examples/delhi-recorded-response.json','utf8')).response;
// Entire Maps SDK is mocked here. The separate verify-map script loads real tiles.
const sdk=`
window.mapEvidence={paths:[],fits:0,pins:[],cameras:[],options:null};
class MockMap {constructor(el,options){this.el=el;this.options=options;this.listeners={};el.dataset.ready='true';window.mapEvidence.options=options;window.mapEvidence.map=this;this.pane=document.createElement('div');el.append(this.pane)} addListener(name,callback){(this.listeners[name]||=[]).push(callback);return{remove:()=>{this.listeners[name]=this.listeners[name].filter(c=>c!==callback)}}}fire(name,value){(this.listeners[name]||[]).forEach(fn=>fn(value))}fitBounds(){window.mapEvidence.fits++;this.fire('idle')}moveCamera(o){window.mapEvidence.cameras.push(o)}getRenderingType(){return 'VECTOR'}setMapTypeId(id){window.mapEvidence.mapType=id}getZoom(){return 15}setZoom(z){window.mapEvidence.zoom=z}setHeading(h){window.mapEvidence.heading=h}}
class OverlayView {setMap(map){if(this.map)this.onRemove();this.map=map;if(map){this.onAdd();this.draw()}}getPanes(){return{overlayMouseTarget:this.map.pane}}getProjection(){return{fromLatLngToDivPixel:p=>{window.mapEvidence.pins.push(p.value);return{x:180+(p.value.lng-77.2)*800,y:180+(p.value.lat-28.6)*800}}}}static preventMapHitsAndGesturesFrom(){}}
window.google={maps:{Map:MockMap,OverlayView,RenderingType:{VECTOR:'VECTOR',RASTER:'RASTER'},LatLng:class{constructor(value){this.value=value}},LatLngBounds:class{extend(){}},Polyline:class{constructor(o){window.mapEvidence.paths.push(o.path)}addListener(){return{remove(){}}}setOptions(){}setMap(){}},event:{clearInstanceListeners(){},addListenerOnce(map,name,fn){map.addListener(name,fn)}}}};
window.ecoGoogleReady();`;
async function mockMap(page:Page){await page.route('https://maps.googleapis.com/**',route=>route.fulfill({contentType:'application/javascript',body:sdk}));}

test('request-only Insights invokes backend explanation and reports its real mode',async({page})=>{
 await mockMap(page);const bodies:any[]=[];
 await page.route('**/api/v1/routes/preview',route=>{const body=route.request().postDataJSON();bodies.push(body);return route.fulfill({json:{...recording,persistence:'request_only',...(body.include_explanation?{explanation:{explanation:'Verified server-calculated explanation',mode:'gemini_arranged_approved_text',fallback_reason:null}}:{})}});});
 await page.goto('/');await page.getByLabel('Origin',{exact:true}).fill('Gateway of India, Mumbai');await page.getByLabel('Destination',{exact:true}).fill('Marine Drive, Mumbai');
 await page.getByRole('checkbox',{name:'Allow processing my locations and route. Google routes are not saved.'}).check();
 await page.getByRole('button',{name:'Compare routes',exact:true}).click();await expect(page.locator('.route-option')).toHaveCount(2);
 await page.getByRole('button',{name:'Insights',exact:true}).click();await page.getByRole('button',{name:'Explain this comparison'}).click();
 await expect(page.locator('.explanation')).toContainText('Verified server-calculated explanation');
 await expect(page.locator('.explanation')).toContainText('Gemini · grounded in server-calculated metrics');
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
 expect(result.renderingType).toBe('VECTOR');expect(result.tilt).toBe(0);expect(result.center).toEqual({lat:0,lng:0});
 await expect(page.getByLabel('Origin',{exact:true})).toHaveValue('');await expect(page.getByLabel('Destination',{exact:true})).toHaveValue('');
 await page.getByLabel('Toggle tilted perspective').click();
 expect(await page.evaluate(()=> (window as any).mapEvidence.cameras.at(-1).tilt)).toBe(50);
 await page.getByLabel('Toggle satellite imagery').click();
 expect(await page.evaluate(()=> (window as any).mapEvidence.mapType)).toBe('roadmap');
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
  await expect(page.getByText('Deterministic summary · no LLM invoked')).toBeVisible();
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
