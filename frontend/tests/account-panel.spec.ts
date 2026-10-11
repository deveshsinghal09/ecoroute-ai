import {test,expect} from '@playwright/test';

for(const size of [{width:1280,height:720},{width:390,height:844}]){
 test(`account panel has a clear sign-in and contains content at ${size.width}x${size.height}`,async({page})=>{
  await page.setViewportSize(size);await page.goto('/');
  await page.getByRole('button',{name:'Connection settings'}).click();
  const dialog=page.getByRole('dialog');
  await expect(dialog.getByRole('heading',{name:'Your account'})).toBeVisible();
  await expect(dialog.getByText('Browsing as a guest',{exact:true})).toBeVisible();
  await expect(dialog.getByRole('button',{name:'Sign in securely'})).toBeVisible();
  await expect(dialog.getByText('API endpoint',{exact:true})).not.toBeVisible();
  await expect(dialog.getByRole('button',{name:'Check backend connection'})).not.toBeVisible();
  await page.evaluate(()=>document.fonts.ready);
  expect(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
  const intro=await dialog.locator('.account-identity').boundingBox(),action=await dialog.getByRole('button',{name:'Sign in securely'}).boundingBox();
  expect(intro!.y+intro!.height).toBeLessThan(action!.y);
  await page.screenshot({path:`../work/account-panel-${size.width}.png`});
  await expect(dialog.locator('.account-brand')).toContainText('EcoRoute AI');
  await expect(dialog.getByText('Connection & data details',{exact:true})).toHaveCount(0);
  await expect(dialog.locator('.account-privacy')).toHaveCount(0);
  await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);
 });
}

test('data view buttons keep an accessible selection state',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Connection settings'}).click();
 const dialog=page.getByRole('dialog');
 await dialog.getByRole('button',{name:'Live services',exact:true}).click();
 await expect(dialog.getByRole('button',{name:'Live services',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(dialog.getByRole('button',{name:'Historical preview',exact:true})).toHaveAttribute('aria-pressed','false');
 await dialog.getByRole('button',{name:'Historical preview',exact:true}).click();
 await expect(dialog.getByRole('button',{name:'Historical preview',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(dialog.getByText('These readings describe that journey, not current conditions.',{exact:false})).toBeVisible();
});
