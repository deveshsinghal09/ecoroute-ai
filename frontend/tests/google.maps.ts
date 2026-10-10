import {test,expect} from '@playwright/test';
test('Journeys initializes Google map and draws selectable real provider geometry',async({page})=>{
 await page.route('https://maps.googleapis.com/**',route=>route.fulfill({contentType:'application/javascript',body:`
 window.mapEvidence={paths:[],fits:0};
 window.google={maps:{Map:class{constructor(el){el.dataset.ready='true'}fitBounds(){window.mapEvidence.fits++}},LatLngBounds:class{extend(){}},Circle:class{setMap(){}},Polyline:class{constructor(o){window.mapEvidence.paths.push(o.path)}addListener(){}setMap(){}},event:{clearInstanceListeners(){}}}};
 window.ecoGoogleReady();` }));
 await page.goto('/');await page.getByRole('button',{name:'Journeys',exact:true}).click();
 await expect(page.getByLabel('Journey map')).toHaveAttribute('data-ready','true');
 const result=await page.evaluate(()=> (window as unknown as {mapEvidence:{paths:{lat:number;lng:number}[][];fits:number}}).mapEvidence);
 expect(result.paths).toHaveLength(2);expect(result.paths[0].length).toBeGreaterThan(10);
 expect(result.paths[0][0].lat).toBeGreaterThan(28);expect(result.paths[0][0].lng).toBeGreaterThan(77);expect(result.fits).toBeGreaterThan(0);
});
test('Google map load failure leaves planner usable',async({page})=>{
 await page.route('https://maps.googleapis.com/**',route=>route.abort());await page.goto('/');
 await page.getByRole('button',{name:'Journeys',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('Google Maps could not load');
 await expect(page.getByRole('heading',{name:'Your next journey'})).toBeVisible();
});
