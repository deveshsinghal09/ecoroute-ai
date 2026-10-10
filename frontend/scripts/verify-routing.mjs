// Explicit live verification: one map load and one comparison. Provider billing applies.
// Supply public landmarks; URLs, keys, tokens and provider error bodies are never logged.
import {chromium} from '@playwright/test';
import {parseArgs} from 'node:util';
import {mkdir,writeFile} from 'node:fs/promises';
const {values}=parseArgs({options:{origin:{type:'string'},destination:{type:'string'},mode:{type:'string',default:'driving'}}});
const modeName={driving:'Drive',walking:'Walk',cycling:'Cycle'}[values.mode];
if(!values.origin||!values.destination||!modeName)throw new Error('Supply --origin, --destination and --mode driving|walking|cycling.');
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
  const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});
  const requests=[];
  page.on('request',r=>{const u=new URL(r.url());if(u.hostname==='127.0.0.1'&&u.pathname.startsWith('/api/'))requests.push({method:r.method(),path:u.pathname});});
  await page.goto('http://127.0.0.1:5173/');
  await page.getByLabel('Origin',{exact:true}).fill(values.origin);
  await page.getByLabel('Destination',{exact:true}).fill(values.destination);
  await page.getByRole('button',{name:modeName,exact:true}).click();
  await page.getByRole('checkbox').check();
  const received=page.waitForResponse(r=>r.url().endsWith('/api/v1/routes/preview')&&r.request().method()==='POST',{timeout:25000});
  await page.getByRole('button',{name:'Compare routes',exact:true}).click();
  let response;
  try {response=await received;} catch {
    await mkdir('../work',{recursive:true});
    await page.screenshot({path:'../work/google-routing-live.png'});
    const diagnostic={requests,notice:await page.locator('.notice').innerText().catch(()=>''),form_valid:await page.locator('form').evaluate(el=>el.checkValidity())};
    console.log(JSON.stringify(diagnostic));
    throw new Error('No routing response received; see the local screenshot and filtered diagnostic.');
  }
  const body=await response.json();
  if(response.ok())await page.locator('.journey-pin').first().waitFor({timeout:15000});
  await page.getByLabel('Origin',{exact:true}).focus();
  const result={http_status:response.status(),error_code:body.error?.code||null,
    route_count:body.routes?.length||0,visible_pins:await page.locator('.journey-pin').count(),
    input_outline:await page.getByLabel('Origin',{exact:true}).evaluate(el=>getComputedStyle(el).outlineStyle),
    providers:[...new Set((body.routes||[]).map(r=>r.routing_source.provider))],
    exposure_available:(body.routes||[]).some(r=>r.estimated_pm25_exposure_ug_h_m3!==null),signed_in:false};
  await mkdir('../work',{recursive:true});
  await page.screenshot({path:'../work/google-routing-live.png'});
  await writeFile('../work/browser-routing-verification.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));process.exitCode=response.ok()?0:1;
} finally {await browser.close();}
