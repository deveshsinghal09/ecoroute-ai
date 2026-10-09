import { test, expect } from '@playwright/test';
test('historical dashboard, route geometry and honest unavailable features',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await page.getByRole('button',{name:'Open journey planner'}).click();await expect(page.getByRole('heading',{name:'Your next journey'})).toBeVisible();
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
  await page.getByRole('button',{name:'Open journey planner'}).click();
  await expect(page.locator('.route-option')).toHaveCount(0);
  await page.getByLabel('Allow this route to be stored in my account.').check();
  await page.getByRole('button',{name:'Compare routes',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Sign in with Cognito');
  expect(await page.evaluate(()=>Object.keys(localStorage))).toEqual([]);
});
test('mobile layout and reduced motion',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');
  await expect(page.getByRole('button',{name:'Play city motion'})).toBeVisible();
  await expect(page.locator('.cinematic-art')).toBeVisible();
  await page.getByRole('button',{name:'Open journey planner'}).click();
  await expect(page.getByRole('heading',{name:'Your next journey'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect(page.locator('.city-backdrop')).toHaveAttribute('href','/assets/ecoroute-city-clear.png');await page.screenshot({path:'../work/frontend-mobile.png',fullPage:true});
});
test('backend connection failure is actionable',async({page})=>{
  await page.route('http://127.0.0.1:8000/**',route=>route.abort());
  await page.goto('/');await page.getByRole('button',{name:'Connection settings'}).click();
  await page.getByRole('button',{name:'Check backend connection'}).click();
  await expect(page.getByRole('status')).toContainText('Cannot reach the backend');
});
test('dialog keeps keyboard focus and returns it on Escape',async({page})=>{
  await page.goto('/');await page.getByRole('button',{name:'Connection settings'}).click();
  await expect(page.getByRole('button',{name:'Close dialog'})).toBeFocused();
  await page.keyboard.press('Shift+Tab');await expect(page.getByRole('button',{name:'Check backend connection'})).toBeFocused();
  await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Close dialog'})).toBeFocused();
  await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Connection settings'})).toBeFocused();
});
test('cancelled authentication shows an error without leaking callback parameters',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/?error=access_denied&state=example');
  await expect(page.getByRole('status')).toContainText('Sign-in was cancelled or expired');
  expect(new URL(page.url()).search).toBe('');expect(errors).toEqual([]);
});
test('WebGL unavailable still permits real route exploration',async({page})=>{
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type:string,...args:unknown[]){
      if(type==='webgl2'||type==='webgl'||type==='experimental-webgl')return null;
      return original.apply(this,[type,...args] as never);
    } as typeof original;
  });
  await page.goto('/');await expect(page.locator('.cinematic-art')).toBeVisible();
  await page.getByRole('button',{name:'Show detail panel'}).click();
  await page.getByRole('button',{name:'Explore recorded routes'}).click();
  await expect(page.locator('.route-map polyline')).toHaveCount(2);
});

test('one city animates trains independently and pause freezes motion',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('button',{name:'3D orbit',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Cinematic',exact:true})).toHaveCount(0);
  await expect(page.locator('.animated-train')).toHaveCount(2);
  for(const path of ['/assets/ecoroute-city-clear.png','/assets/ecoroute-tram.png'])expect((await page.request.get(path)).ok()).toBe(true);
  const train=page.locator('.animated-train').first();
  const frozen=await train.getAttribute('data-position');await page.waitForTimeout(150);
  expect(await train.getAttribute('data-position')).toBe(frozen);
  await page.getByRole('button',{name:'Play city motion'}).click();
  await expect.poll(()=>train.getAttribute('data-position')).not.toBe(frozen);
  await page.getByRole('button',{name:'Pause city motion'}).click();
  const paused=await train.getAttribute('data-position');await page.waitForTimeout(150);
  expect(await train.getAttribute('data-position')).toBe(paused);
  await page.screenshot({path:'../work/frontend-animated-city.png'});
});

test('desktop dashboard fits at 100 percent zoom on laptop screens',async({page})=>{
 for(const size of [{width:1366,height:768},{width:1280,height:720},{width:1536,height:864}]){
  await page.setViewportSize(size);await page.goto('/');
  expect(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight+1)).toBe(true);
  await page.getByRole('button',{name:'Open journey planner'}).click();
  expect(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight+1)).toBe(true);
 }
});
