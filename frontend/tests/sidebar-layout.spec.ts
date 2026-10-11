import {test,expect} from '@playwright/test';
import recording from '../../examples/delhi-recorded-response.json' with {type:'json'};
for(const size of [{width:1280,height:720},{width:1366,height:768},{width:1024,height:640},{width:390,height:844}]){
 test(`sidebar fits ${size.width}x${size.height}`,async({page})=>{
 await page.setViewportSize(size);await page.goto('/');
 await expect(page.getByTestId('selected-pm25')).toBeVisible();
 await page.evaluate(()=>document.fonts.ready);
 const problems=await page.locator('.instrument-rail').evaluate(rail=>{
 const issues:string[]=[];
 for(const card of rail.children){const b=card.getBoundingClientRect();if(innerWidth>740&&b.bottom>rail.getBoundingClientRect().bottom+1)issues.push(card.className+' exceeds rail by '+Math.round(b.bottom-rail.getBoundingClientRect().bottom));for(const child of card.querySelectorAll('*')){if(child.closest('svg'))continue;const r=child.getBoundingClientRect();if(r.width&&r.height&&(r.left<b.left-1||r.right>b.right+1||r.bottom>b.bottom+1))issues.push(child.className||child.tagName);}}
 if(innerWidth>740&&rail.getBoundingClientRect().bottom>innerHeight)issues.push('rail exceeds viewport');return issues;
 });expect(problems).toEqual([]);
 await expect(page.locator(".brand")).toContainText("EcoRoute AI");
 await expect(page.locator(".selected-route-air .small-badge")).toHaveCount(0);
 if(size.width>740){const air=await page.locator(".selected-route-air").boundingBox(),exposure=await page.locator(".selected-route-exposure").boundingBox();expect(Math.abs(air!.height-exposure!.height)).toBeLessThanOrEqual(1);}
 const gauge=await page.locator('.air-ring').evaluate(el=>{
   const ring=el.getBoundingClientRect(),range=document.createRange();range.selectNodeContents(el.querySelector('strong')!);const value=range.getBoundingClientRect();range.selectNodeContents(el.querySelector('span')!);const unit=range.getBoundingClientRect();
   return {fits:value.left>=ring.left&&value.right<=ring.right&&unit.left>=ring.left&&unit.right<=ring.right&&value.top>=ring.top&&unit.bottom<=ring.bottom,separated:value.bottom<=unit.top};
 });expect(gauge).toEqual({fits:true,separated:true});
 const readability=await page.locator('.instrument-rail').evaluate(rail=>{
   const failures:string[]=[];
   const rgb=(color:string)=>color.match(/[\d.]+/g)!.slice(0,3).map(Number);
   const luminance=(color:string)=>rgb(color).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
   for(const el of rail.querySelectorAll('p,.rail-small,.small-badge,.selected-route-context span,.selected-coverage-row span')){
     if(!el.getBoundingClientRect().height)continue;
     const style=getComputedStyle(el);if(parseFloat(style.fontSize)<11)failures.push('small text: '+el.className);
     let parent:Element|null=el,bg='';
     while(parent){const c=getComputedStyle(parent).backgroundColor;if(c!=='rgba(0, 0, 0, 0)'){bg=c;break;}parent=parent.parentElement;}
     if(bg){const a=luminance(style.color),b=luminance(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);if(ratio<4.5)failures.push('low contrast: '+el.className);}
   }
   return failures;
 });expect(readability).toEqual([]);
 await page.getByRole('button',{name:'Insights',exact:true}).click();
 await expect(page.getByText('Check forecasting model',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Completed local training evaluation',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Sources & route limitations',{exact:true})).toHaveCount(0);
 if(size.width===1280)await page.screenshot({path:'../work/sidebar-balanced.png'});
 });
}

test('empty readings keep the balanced cards and unit inside their bounds',async({page})=>{
 await page.setViewportSize({width:1024,height:640});await page.goto('/');
 await page.getByRole('button',{name:'Connection settings'}).click();await page.getByRole('button',{name:'Live services',exact:true}).click();
 await page.getByRole('button',{name:'Close dialog'}).click();await page.evaluate(()=>document.fonts.ready);
 await expect(page.getByTestId('selected-pm25')).toHaveText('—');
 const fits=await page.locator('.instrument-rail').evaluate(el=>Array.from(el.children).every(c=>c.getBoundingClientRect().bottom<=el.getBoundingClientRect().bottom+1));expect(fits).toBe(true);
 const unit=await page.locator('.air-ring span').boundingBox(),number=await page.getByTestId('selected-pm25').boundingBox();
 expect(number!.y+number!.height).toBeLessThanOrEqual(unit!.y);
});

test('long test-only concentration values stay inside the dial without colliding with units',async({page})=>{
 // Artificial large metrics exercise text layout only, not environmental validity.
 const response=structuredClone(recording.response);
 for(const r of response.routes){r.duration_s=360;r.estimated_pm25_exposure_ug_h_m3=123.45;r.pm25_coverage_fraction=1;}
 await page.route('**/api/v1/routes/preview',route=>route.fulfill({json:response}));
 await page.setViewportSize({width:1024,height:640});await page.goto('/');
 await page.getByRole('button',{name:'Connection settings'}).click();await page.getByRole('button',{name:'Live services',exact:true}).click();await page.getByRole('button',{name:'Close dialog'}).click();
 await page.getByRole('button',{name:'Open journey planner'}).click();
 await page.getByLabel('Origin',{exact:true}).fill('India Gate');await page.getByLabel('Destination',{exact:true}).fill('Connaught Place');
 await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Compare routes',exact:true}).click();
 await expect(page.getByTestId('selected-pm25')).toHaveText('1234.5');await page.evaluate(()=>document.fonts.ready);
 await expect.poll(()=>page.locator('.air-ring').evaluate(el=>{
  const ring=el.getBoundingClientRect(),range=document.createRange();range.selectNodeContents(el.querySelector('strong')!);const value=range.getBoundingClientRect();range.selectNodeContents(el.querySelector('span')!);const unit=range.getBoundingClientRect();
  return value.left>=ring.left&&value.right<=ring.right&&value.bottom<=unit.top&&unit.bottom<=ring.bottom;
 })).toBe(true);
});
