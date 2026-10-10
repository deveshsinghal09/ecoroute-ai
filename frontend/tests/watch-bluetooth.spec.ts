import {test,expect} from '@playwright/test';

// Synthetic browser sensor events only. These tests never open a physical Bluetooth chooser.
async function mockBluetooth(page:import('@playwright/test').Page,missing=false){
 await page.addInitScript(({missing})=>{
  class Sensor extends EventTarget {
   value?:DataView;properties={notify:true,read:true};
   async startNotifications(){return this;}async stopNotifications(){return this;}
   async readValue(){return new DataView(Uint8Array.from([42]).buffer);}
  }
  const heart=new Sensor(),battery=new Sensor(),device=new EventTarget() as EventTarget&{gatt:unknown};
  const server={connected:true,async connect(){return server;},disconnect(){server.connected=false;},
   async getPrimaryService(name:string){if(missing&&name==='heart_rate')throw new Error('PRIVATE_VENDOR_PACKET');return {async getCharacteristic(){return name==='heart_rate'?heart:battery;}};}};
  device.gatt=server;
  Object.defineProperty(navigator,'bluetooth',{configurable:true,value:{async requestDevice(){(window as unknown as {chooserCount:number}).chooserCount++;server.connected=true;return device;}}});
  Object.assign(window,{chooserCount:0,emitTestHeart:(bytes:number[])=>{heart.value=new DataView(Uint8Array.from(bytes).buffer);heart.dispatchEvent(new Event('characteristicvaluechanged'));}});
 },{missing});
}

test('Bluetooth consent gates the chooser and received readings update the 3D watch',async({page})=>{
 await mockBluetooth(page);await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();
 const watch=page.locator('.eco-watch');const connect=watch.getByRole('button',{name:'Connect Bluetooth',exact:true});
 await expect(connect).toBeDisabled();expect(await page.evaluate(()=>(window as unknown as {chooserCount:number}).chooserCount)).toBe(0);
 await watch.getByLabel('Allow this browser to read my watch over Bluetooth').check();await connect.click();
 await expect(watch.getByText('Connected. Waiting for the watch',{exact:false})).toBeVisible();
 await expect(watch.locator('.eco-watch-demo')).toHaveText('WAITING FOR READING');
 await page.evaluate(()=>(window as unknown as {emitTestHeart:(v:number[])=>void}).emitTestHeart([6,76]));
 await expect(watch.locator('.eco-watch-readout')).toContainText('Heart 76 BPM');await expect(watch.locator('.eco-watch-readout')).toContainText('Battery 42%');
 await expect(watch.locator('.eco-watch-readout')).toContainText('Health score unavailable');await expect(watch.locator('.eco-watch-demo')).toHaveText('READING RECEIVED');
 await watch.getByRole('button',{name:'Watch Heart',exact:true}).click();await expect(watch.locator('.eco-watch-readout')).toContainText('1 received readings');
 await watch.getByRole('button',{name:'Watch Wellness',exact:true}).click();await expect(watch.locator('.eco-watch-readout')).toContainText('Blood oxygen Unavailable');
 await watch.getByRole('button',{name:'Watch Home',exact:true}).click();await expect(watch.locator('.eco-watch-viewport')).toHaveAttribute('data-renderer','three');
 await watch.locator('.eco-watch-viewport').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/watch-synthetic-bluetooth.png'});
 await watch.getByRole('button',{name:'Disconnect & clear',exact:true}).click();
 await page.evaluate(()=>(window as unknown as {emitTestHeart:(v:number[])=>void}).emitTestHeart([6,80]));
 await expect(watch.locator('.eco-watch-readout')).toContainText('No readings available');await expect(watch.locator('.eco-watch-demo')).toHaveText('NOT CONNECTED');
});

test('unknown vendor services stop integration without decoding or leaking errors',async({page})=>{
 await mockBluetooth(page,true);await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();
 await page.getByLabel('Allow this browser to read my watch over Bluetooth').check();await page.getByRole('button',{name:'Connect Bluetooth',exact:true}).click();
 await expect(page.getByText('This device did not expose standard Heart Rate',{exact:false})).toBeVisible();
 await expect(page.getByText('PRIVATE_VENDOR_PACKET')).toHaveCount(0);await expect(page.locator('.eco-watch-readout')).toContainText('No readings available');
});

test('revocation clears readings and stale heart rate is not presented as current',async({page})=>{
 await page.clock.install();
 await mockBluetooth(page);await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();
 const watch=page.locator('.eco-watch');await watch.getByLabel('Allow this browser to read my watch over Bluetooth').check();await watch.getByRole('button',{name:'Connect Bluetooth',exact:true}).click();
 await page.evaluate(()=>(window as unknown as {emitTestHeart:(v:number[])=>void}).emitTestHeart([0,76]));
 await expect(watch.locator('.eco-watch-readout')).toContainText('Heart 76 BPM');
 await expect(watch.locator('.eco-watch-readout')).toContainText('Battery 42%');
 await page.clock.fastForward(65000);
 await expect(watch.locator('.eco-watch-readout')).toContainText('Heart Unavailable');await expect(watch.getByText('stale; no current reading',{exact:false})).toBeVisible();
 await page.clock.fastForward(250000);await expect(watch.locator('.eco-watch-readout')).toContainText('Battery Unavailable');
 await watch.getByLabel('Allow this browser to read my watch over Bluetooth').uncheck();await expect(watch.locator('.eco-watch-demo')).toHaveText('NOT CONNECTED');
 await expect(watch.getByRole('button',{name:'Connect Bluetooth',exact:true})).toBeDisabled();
});

test('leaving Wearable closes Bluetooth and does not reconnect without consent',async({page})=>{
 await mockBluetooth(page);await page.goto('/');await page.getByRole('button',{name:'Wearable',exact:true}).click();
 await page.getByLabel('Allow this browser to read my watch over Bluetooth').check();await page.getByRole('button',{name:'Connect Bluetooth',exact:true}).click();
 await page.evaluate(()=>(window as unknown as {emitTestHeart:(v:number[])=>void}).emitTestHeart([0,76]));
 await expect(page.locator('.eco-watch-readout')).toContainText('Heart 76 BPM');
 await page.getByRole('button',{name:'Journeys',exact:true}).click();await page.getByRole('button',{name:'Wearable',exact:true}).click();
 await expect(page.getByLabel('Allow this browser to read my watch over Bluetooth')).not.toBeChecked();
 await expect(page.locator('.eco-watch-readout')).toContainText('No readings available');
 expect(await page.evaluate(()=>(window as unknown as {chooserCount:number}).chooserCount)).toBe(1);
});
