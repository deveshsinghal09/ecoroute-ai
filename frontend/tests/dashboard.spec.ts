import { test, expect } from '@playwright/test';
test('historical dashboard, route geometry and honest unavailable features',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.getByRole('heading',{name:'Your next journey'})).toBeVisible();
  await expect(page.getByText('Historical preview · 09 Oct 2026')).toBeVisible();
  await expect(page.getByRole('button',{name:'Cycle',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Explore recorded routes'}).click();
  await expect(page.locator('.route-map polyline')).toHaveCount(2);
  await page.getByRole('button',{name:'Alternative route'}).click();
  await expect(page.locator('.route-option.chosen')).toContainText('Alternative route');
  await page.getByRole('button',{name:'Wearable',exact:true}).click();
  await expect(page.getByText('Hardware bridge not connected')).toBeVisible();
  await page.getByRole('button',{name:'Insights',exact:true}).click();
  await page.getByRole('button',{name:'Explain this comparison'}).click();
  await expect(page.getByText('Deterministic summary · no LLM invoked')).toBeVisible();
  expect(errors).toEqual([]);
});
test('live mode clears preview and cannot silently authenticate',async({page})=>{
  await page.goto('/');await page.getByRole('button',{name:'Connection settings'}).click();
  await page.getByRole('button',{name:'Live services',exact:true}).click();
  await page.getByRole('button',{name:'Sign in with Cognito'}).click();
  await expect(page.getByRole('status')).toContainText('Cognito is not configured');
  await page.getByRole('button',{name:'Close dialog'}).click();
  await expect(page.locator('.route-option')).toHaveCount(0);
  await page.getByLabel('Allow this route to be stored in my account.').check();
  await page.getByRole('button',{name:'Compare routes',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Sign in with Cognito');
  expect(await page.evaluate(()=>Object.keys(localStorage))).toEqual([]);
});
test('mobile layout and reduced motion',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');
  await expect(page.getByRole('button',{name:'Play city motion'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Your next journey'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect(page.locator('.city-canvas canvas')).toBeVisible();await page.waitForTimeout(1500);await page.screenshot({path:'../work/frontend-mobile.png',fullPage:true});
});
test('backend connection failure is actionable',async({page})=>{
  await page.route('http://127.0.0.1:8000/**',route=>route.abort());
  await page.goto('/');await page.getByRole('button',{name:'Connection settings'}).click();
  await page.getByRole('button',{name:'Check backend connection'}).click();
  await expect(page.getByRole('status')).toContainText('Cannot reach the backend');
});
