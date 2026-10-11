import {test,expect,type Page} from '@playwright/test';

// Explicit synthetic test fixtures. These values never ship as an application fallback.
const labels=['heart_rate','blood_pressure','oxygen_saturation','steps','sleep','calories_burned','resting_heart_rate','respiratory_rate'];
function summary(){const now=new Date(),stamp=now.toISOString(),day=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
 const values=[76,{systolic:120,diastolic:80},98,8420,26400,320,61,16],units=['bpm','mmHg','%','count','s','kcal','bpm','breaths/min'];
 return {status:'available',selected_date:day,timezone:'Asia/Kolkata',fetched_at:stamp,payload_generated_at:stamp,last_synchronization_at:null,retrieval:'fresh',calorie_basis:'active',sleep_sessions:[],warnings:[],skipped_records:0,medical_assessment:false,
 metrics:Object.fromEntries(labels.map((name,i)=>[name,{value:values[i],unit:units[i],status:'available',timestamp:stamp,source_applications:['test.fixture'],resolution:'sample',stale:false,warnings:[]}]))};}
async function open(page:Page){await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();return page.getByRole('region',{name:'Health Connect metrics'});}

test('consent, scoped pairing, eight metrics, refresh and revocation',async({page})=>{
 let requests=0;await page.route('**/api/v1/wearables/health-connect/summary**',async route=>{requests++;expect(route.request().headers().authorization).toBe('Bearer SYNTHETIC_LOCAL_PAIRING_KEY');expect(new URL(route.request().url()).searchParams.get('timezone_name')).toBe(await page.evaluate(()=>Intl.DateTimeFormat().resolvedOptions().timeZone));await route.fulfill({json:summary()});});
 const panel=await open(page);await panel.getByLabel('Local pairing key').fill('SYNTHETIC_LOCAL_PAIRING_KEY');
 await expect(panel.getByRole('button',{name:'Connect & read'})).toBeDisabled();expect(requests).toBe(0);
 await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:'Connect & read'}).click();
 await expect(panel.locator('[data-metric=heart_rate] dd')).toContainText('76');await expect(panel.locator('[data-metric=blood_pressure] dd')).toContainText('120 / 80');await expect(panel.locator('[data-metric=sleep] dd')).toContainText('7h 20m');
 await expect(panel.locator('dl>div')).toHaveCount(8);await expect(panel.getByText('Last successful update:',{exact:false})).toBeVisible();
 const watch=page.getByRole('region',{name:'EcoRoute 3D smartwatch preview'});await expect(watch).toContainText('HEALTH CONNECT RECORDS');
 await panel.getByRole('button',{name:'Refresh',exact:true}).click();await expect.poll(()=>requests).toBe(2);
 await panel.getByRole('checkbox').uncheck();await expect(panel.getByRole('button',{name:'Connect & read'})).toBeDisabled();await expect(panel.locator('.no-reading')).toHaveCount(8);await expect(watch).not.toContainText('HEALTH CONNECT RECORDS');
 expect(await page.evaluate(()=>sessionStorage.getItem('health-connect-key')||localStorage.getItem('health-connect-key'))).toBeNull();
});
test('empty response and phone outage do not substitute readings; retry remains usable',async({page})=>{
 let fail=false;await page.route('**/api/v1/wearables/health-connect/summary**',async route=>{if(fail){await route.fulfill({status:503,json:{error:{code:'health_connect_phone_unreachable'}}});return;}const result=summary();for(const metric of Object.values(result.metrics)){metric.value=null as never;metric.status='unavailable';}await route.fulfill({json:result});});
 const panel=await open(page);await panel.getByLabel('Local pairing key').fill('SYNTHETIC_LOCAL_PAIRING_KEY');await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:'Connect & read'}).click();await expect(panel.locator('.no-reading')).toHaveCount(8);
 fail=true;await panel.getByRole('button',{name:'Refresh',exact:true}).click();await expect(panel.getByRole('alert')).toContainText('Cannot reach your phone');await expect(panel.locator('.no-reading')).toHaveCount(8);await expect(panel.getByRole('button',{name:'Retry connection'})).toBeEnabled();
 fail=false;await panel.getByRole('button',{name:'Retry connection'}).click();await expect(panel.getByRole('button',{name:'Refresh',exact:true})).toBeEnabled();
});
test('date changes clear previous readings and mobile metrics fit without horizontal overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.route('**/api/v1/wearables/health-connect/summary**',route=>route.fulfill({json:summary()}));
 const panel=await open(page);await panel.getByLabel('Local pairing key').fill('SYNTHETIC_LOCAL_PAIRING_KEY');await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:'Connect & read'}).click();await expect(panel.locator('[data-metric=steps] dd')).toContainText('8,420');
 await panel.locator('dl').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/health-connect-mobile.png'});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 const yesterday=new Date();yesterday.setDate(yesterday.getDate()-1);const day=`${yesterday.getFullYear()}-${String(yesterday.getMonth()+1).padStart(2,'0')}-${String(yesterday.getDate()).padStart(2,'0')}`;
 await panel.getByLabel('Day',{exact:true}).fill(day);await expect(panel.locator('.no-reading')).toHaveCount(8);
 await expect(panel.getByText('Refresh to load this day.')).toBeVisible();await expect(panel.getByText('Last successful update:',{exact:false})).toHaveCount(0);
 await page.getByRole('button',{name:'Insights',exact:true}).click();await page.getByRole('button',{name:'Wearable',exact:true}).click();await expect(page.getByRole('region',{name:'Health Connect metrics'}).getByRole('checkbox')).not.toBeChecked();
});
