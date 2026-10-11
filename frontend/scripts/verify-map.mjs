// Explicit local browser verification. Loads Google once; may incur a map-load charge.
// Never logs network URLs, key values, provider response bodies or browser errors.
import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
  const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});
  await page.goto(process.env.MAP_VERIFY_URL||'http://127.0.0.1:5173/');
  const host=page.getByLabel('Journey map',{exact:true});
  try {await host.waitFor({state:'visible',timeout:20000});await page.waitForFunction(()=>document.querySelector('.google-map-host')?.getAttribute('data-tiles-loaded')==='true',{},{timeout:20000});} catch { /* Report safely below. */ }
  let threeD=false,twoD=false,renderer='unknown',tilt=0;
  if(await host.getAttribute('data-tiles-loaded').catch(()=>null)==='true'){
    await page.getByLabel('Show 3D map',{exact:true}).click();
    try{await page.waitForFunction(()=>Number(document.querySelector('.google-map-host')?.getAttribute('data-camera-tilt'))>0,{}, {timeout:10000});}catch{/* report unsupported honestly */}
    renderer=await host.getAttribute('data-rendering-type')||'unknown';
    tilt=Number(await host.getAttribute('data-camera-tilt')||0);threeD=renderer==='vector'&&tilt>0;
    await page.getByLabel('Show 2D map',{exact:true}).click();
    twoD=await page.getByLabel('Show 2D map',{exact:true}).getAttribute('aria-pressed')==='true';
  }
  const tilesLoaded=await host.getAttribute('data-tiles-loaded').catch(()=>null)==='true';
  const authFailure=await page.getByText('Google Maps could not authorize this website.',{exact:false}).count()>0;
  await mkdir('../work',{recursive:true});
  await page.screenshot({path:'../work/google-map-live.png'});
  console.log(JSON.stringify({tiles_loaded:tilesLoaded,authorization_failure:authFailure,renderer,three_d_verified:threeD,three_d_tilt:tilt,two_d_verified:twoD,screenshot:'work/google-map-live.png',signed_in:false}));
  process.exitCode=tilesLoaded&&!authFailure?0:1;
} finally {await browser.close();}
