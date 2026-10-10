// Explicit local browser verification. Loads Google once; may incur a map-load charge.
// Never logs network URLs, key values, provider response bodies or browser errors.
import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
  const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});
  await page.goto('http://127.0.0.1:5173/');
  const host=page.getByLabel('Journey map',{exact:true});
  try {await host.waitFor({state:'visible',timeout:20000});await page.waitForFunction(()=>document.querySelector('.google-map-host')?.getAttribute('data-tiles-loaded')==='true',{},{timeout:20000});} catch { /* Report safely below. */ }
  const tilesLoaded=await host.getAttribute('data-tiles-loaded').catch(()=>null)==='true';
  const authFailure=await page.getByText('Google Maps could not authorize this website.',{exact:false}).count()>0;
  await mkdir('../work',{recursive:true});
  await page.screenshot({path:'../work/google-map-live.png'});
  console.log(JSON.stringify({tiles_loaded:tilesLoaded,authorization_failure:authFailure,screenshot:'work/google-map-live.png',signed_in:false}));
  process.exitCode=tilesLoaded&&!authFailure?0:1;
} finally {await browser.close();}
