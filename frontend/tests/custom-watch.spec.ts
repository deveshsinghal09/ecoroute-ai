import {test,expect} from '@playwright/test';
test('original 3D watch renders and all screens and settings work',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();
 const watch=page.getByRole('region',{name:'EcoRoute 3D smartwatch preview'});
 await expect(watch.locator('.eco-watch-viewport')).toHaveAttribute('data-renderer','three',{timeout:30000});
 for(const name of ['Heart','Activity','Sleep','Wellness','Notifications','Settings']){await watch.getByRole('button',{name:`Watch ${name}`,exact:true}).click();await expect(watch.getByRole('button',{name:`Watch ${name}`,exact:true})).toHaveAttribute('aria-pressed','true');}
 await watch.getByLabel('Screen theme').selectOption('#b0ef75');await watch.getByRole('slider',{name:'Watch brightness'}).fill('60');await expect(watch.getByText('Brightness · 60%')).toBeVisible();
 await watch.getByLabel('Preview notification cards').uncheck();await watch.getByRole('button',{name:'Watch Notifications',exact:true}).click();await expect(watch.locator('.eco-watch-readout')).toContainText('No notifications sent');
 await watch.getByRole('button',{name:'Watch crown home',exact:true}).click();await expect(watch.locator('.eco-watch-readout')).toContainText('Health 87/100');
 const box=await watch.locator('.eco-watch-viewport').boundingBox();if(!box)throw Error('No viewport');await page.mouse.move(box.x+box.width*.8,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.25,box.y+box.height*.5,{steps:10});await page.mouse.up();await expect(watch.getByRole('button',{name:'Watch Heart',exact:true})).toHaveAttribute('aria-pressed','true');
 await watch.getByRole('button',{name:'Watch Home',exact:true}).click();await watch.scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/custom-watch-desktop.png'});expect(errors).toEqual([]);
});
test('watch fits mobile and preserves accessible fallback without WebGL',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){if(String(type).includes('webgl'))return null;return original.call(this,type,...args)} as typeof original;});
 await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();const watch=page.getByRole('region',{name:'EcoRoute 3D smartwatch preview'});
 await expect(watch.getByText('3D unavailable.',{exact:false})).toBeVisible({timeout:30000});await watch.getByRole('button',{name:'Watch Activity',exact:true}).click();await expect(watch.locator('.eco-watch-readout')).toContainText('8,420 steps');
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
 await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(150);const zoom=Math.min(b.height/7.35,b.width/3.6);await page.mouse.click(b.x+b.width/2+1.31*zoom,b.y+b.height/2-.21*zoom);await expect(watch.getByRole('button',{name:'Watch Home',exact:true})).toHaveAttribute('aria-pressed','true');
});
