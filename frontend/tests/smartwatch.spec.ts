import {test,expect} from '@playwright/test';
test('watch screens, keyboard, swipe and device isolation',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();
 const watch=page.getByRole('region',{name:'Interactive smartwatch demo'});
 await expect(watch).toBeVisible();await expect(watch.getByText('87',{exact:false}).first()).toBeVisible();
 await watch.getByRole('button',{name:'Show Heart health',exact:true}).click();await expect(watch.locator('.swh-reading')).toHaveText('76BPM');
 await watch.getByRole('button',{name:'Next watch screen'}).click();await expect(watch.getByText('7h 42m',{exact:false})).toBeVisible();
 const face=watch.locator('.swh-dial-face');await face.focus();await page.keyboard.press('ArrowRight');await expect(watch.locator('.swh-steps')).toContainText('8,420');
 const bounds=await face.boundingBox();if(!bounds)throw Error('No watch face');
 await page.mouse.move(bounds.x+150,bounds.y+75);await page.mouse.down();await page.mouse.move(bounds.x+30,bounds.y+75);await page.mouse.up();
 await expect(watch.getByRole('button',{name:'Show Home',exact:true})).toHaveAttribute('aria-pressed','true');
 await watch.getByRole('button',{name:'Show Sleep',exact:true}).click();await watch.getByRole('button',{name:'Watch home',exact:true}).click();await expect(watch.getByRole('button',{name:'Show Home',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(watch).toContainText('placeholders');await expect(page.getByRole('button',{name:'Read latest measurement'})).toBeDisabled();
 await page.screenshot({path:'test-results/smartwatch-desktop.png'});
});
test('entire watch geometry fits its container on mobile',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();
 const watch=page.locator('.smartwatch-health');await watch.scrollIntoViewIfNeeded();
 const geometry=await watch.evaluate(root=>{const area=root.querySelector('.swh-watch-container').getBoundingClientRect();return [...root.querySelectorAll('.swh-dial,.swh-top-strap,.swh-bottom-strap,.swh-buckle')].map(el=>{const r=el.getBoundingClientRect();return {left:r.left-area.left,right:area.right-r.right,top:r.top-area.top,bottom:area.bottom-r.bottom};});});
 for(const box of geometry){expect(box.left).toBeGreaterThanOrEqual(0);expect(box.right).toBeGreaterThanOrEqual(0);expect(box.top).toBeGreaterThanOrEqual(0);expect(box.bottom).toBeGreaterThanOrEqual(0);}
 await expect(watch.locator('.swh-pulse')).toHaveCount(0);
 await watch.getByRole('button',{name:'Show Heart health',exact:true}).click();expect(await watch.locator('.swh-pulse').evaluate(el=>getComputedStyle(el).animationName)).toBe('none');
 await page.screenshot({path:'test-results/smartwatch-mobile.png',fullPage:true});
});
