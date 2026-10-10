import {test,expect} from '@playwright/test';
test('original 3D watch renders and all screens and settings work',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();
 const watch=page.getByRole('region',{name:'EcoRoute 3D smartwatch preview'});
 await expect(watch.locator('.eco-watch-viewport')).toHaveAttribute('data-renderer','three',{timeout:30000});
 for(const name of ['Heart','Activity','Sleep','Wellness','Notifications','Settings']){await watch.getByRole('button',{name:`Watch ${name}`,exact:true}).click();await expect(watch.getByRole('button',{name:`Watch ${name}`,exact:true})).toHaveAttribute('aria-pressed','true');}
 await watch.getByLabel('Screen theme').selectOption('#b0ef75');await watch.getByRole('slider',{name:'Watch brightness'}).fill('60');await expect(watch.getByText('Brightness · 60%')).toBeVisible();
 await watch.getByLabel('Notification preview').uncheck();await watch.getByRole('button',{name:'Watch Notifications',exact:true}).click();await expect(watch.locator('.eco-watch-readout')).toContainText('No readings available');
 await watch.getByRole('button',{name:'Watch crown home',exact:true}).click();await expect(watch.locator('.eco-watch-readout')).toContainText('No readings available');
 await watch.locator('.eco-watch-viewport').scrollIntoViewIfNeeded();const box=await watch.locator('.eco-watch-viewport').boundingBox();if(!box)throw Error('No viewport');await page.mouse.move(box.x+box.width*.8,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.25,box.y+box.height*.5,{steps:10});await page.mouse.up();await expect(watch.getByRole('button',{name:'Watch Heart',exact:true})).toHaveAttribute('aria-pressed','true');
 await watch.getByRole('button',{name:'Watch Settings',exact:true}).click();await watch.getByRole('slider',{name:'Watch brightness'}).fill('100');await watch.getByRole('button',{name:'Watch Home',exact:true}).click();await watch.locator('.eco-watch-viewport').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/custom-watch-desktop.png'});expect(errors).toEqual([]);
});
test('watch fits mobile and preserves accessible fallback without WebGL',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){if(String(type).includes('webgl'))return null;return original.call(this,type,...args)} as typeof original;});
 await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();const watch=page.getByRole('region',{name:'EcoRoute 3D smartwatch preview'});
 await expect(watch.getByText('3D unavailable.',{exact:false})).toBeVisible({timeout:30000});await watch.getByRole('button',{name:'Watch Activity',exact:true}).click();await expect(watch.locator('.eco-watch-readout')).toContainText('No readings available');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test('mobile 3D render and reduced-motion preference',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();const watch=page.getByRole('region',{name:'EcoRoute 3D smartwatch preview'});
 await expect(watch.locator('.eco-watch-viewport')).toHaveAttribute('data-renderer','three',{timeout:30000});await expect(watch.locator('.eco-watch-viewport')).toHaveAttribute('data-motion','paused');
 await watch.getByRole('button',{name:'Watch Heart',exact:true}).click();await watch.locator('.eco-watch-viewport').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/custom-watch-mobile.png'});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test('watch tap, crown and motion pause operate in the 3D scene',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();const watch=page.getByRole('region',{name:'EcoRoute 3D smartwatch preview'});const viewport=watch.locator('.eco-watch-viewport');await expect(viewport).toHaveAttribute('data-renderer','three');await viewport.scrollIntoViewIfNeeded();await expect(viewport).toHaveAttribute('data-motion','active');await watch.getByRole('button',{name:'Pause motion',exact:true}).click();await expect(viewport).toHaveAttribute('data-motion','paused');
 await viewport.scrollIntoViewIfNeeded();const b=await viewport.boundingBox();if(!b)throw Error('No watch');await page.mouse.click(b.x+b.width/2,b.y+b.height/2);await expect(watch.getByRole('button',{name:'Watch Heart',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(150);const zoom=Math.min(b.height/8.6,b.width/4.9);await page.mouse.click(b.x+b.width/2+1.45*1.31*zoom,b.y+b.height/2-.39*zoom);await expect(watch.getByRole('button',{name:'Watch Home',exact:true})).toHaveAttribute('aria-pressed','true');
});
test('watch artwork keeps every label inside screen and metric card bounds',async({page})=>{
 await page.goto('/');
 const violations=await page.evaluate(async()=>{
  const {paintScreen}=await import('/src/wearable/watchScreen.ts');const {watchPages}=await import('/src/wearable/watchData.ts');
  await document.fonts.ready;const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=1200;const c=canvas.getContext('2d')!;const failures:string[]=[];let current='';
  const fill=c.fillText.bind(c);c.fillText=(text,x,y)=>{const m=c.measureText(text),left=c.textAlign==='center'?x-m.width/2:c.textAlign==='right'?x-m.width:x;
   if(left<20||left+m.width>492||y-m.actualBoundingBoxAscent<0||y+m.actualBoundingBoxDescent>590)failures.push(`${current}: ${text}`);
   if(current==='Home'&&y>=390&&y<=540){const edge=x<256?249:486;if(left+m.width>edge)failures.push(`card: ${text}`);}fill(text,x,y);};
  for(const data of [undefined,{source:'bluetooth' as const,heartRate:76,battery:42,heartSamples:[{at:'2026-10-11T08:00:00Z',bpm:76},{at:'2026-10-11T08:00:01Z',bpm:77}]}])for(const name of watchPages){current=name;paintScreen(canvas,name,data,{accent:'#ff914d',brightness:100,motion:false,previewAlerts:true},new Date('2026-10-10T08:00:00Z'));}
  return failures;
 });expect(violations).toEqual([]);
 await page.getByRole('button',{name:'Wearable',exact:true}).click();await expect(page.locator('.wearable-panel')).toHaveCSS('background-color','rgb(211, 231, 241)');
});
