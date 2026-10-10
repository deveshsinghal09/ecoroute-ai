import type {WatchData} from './watchData';

// Only Bluetooth SIG Heart Rate and Battery services are accessed. No proprietary decoding.
export type HeartReading = {bpm:number;contact:'detected'|'unsupported';rrSeconds:number[]};
export function decodeHeartRate(value:DataView):HeartReading {
  if(value.byteLength<2)throw new Error('Incomplete heart-rate packet.');
  const flags=value.getUint8(0);let offset=1;
  const requireBytes=(n:number)=>{if(offset+n>value.byteLength)throw new Error('Incomplete heart-rate packet.');};
  const wide=Boolean(flags&1);requireBytes(wide?2:1);
  const bpm=wide?value.getUint16(offset,true):value.getUint8(offset);offset+=wide?2:1;
  if(bpm<20||bpm>250)throw new Error('Heart-rate reading outside the accepted range.');
  if((flags&4)&&!(flags&2))throw new Error('The sensor reports no skin contact.');
  if(flags&8){requireBytes(2);offset+=2;} // Energy is cumulative kJ, not daily kcal.
  const rrSeconds:number[]=[];
  if(flags&16){if(offset===value.byteLength||(value.byteLength-offset)%2)throw new Error('Incomplete RR interval packet.');
    while(offset<value.byteLength){rrSeconds.push(value.getUint16(offset,true)/1024);offset+=2;}}
  if(offset!==value.byteLength)throw new Error('Unexpected heart-rate packet length.');
  return {bpm,contact:flags&4?'detected':'unsupported',rrSeconds};
}

interface Characteristic extends EventTarget {value?:DataView;properties:{notify?:boolean;indicate?:boolean;read?:boolean};startNotifications():Promise<Characteristic>;stopNotifications():Promise<Characteristic>;readValue():Promise<DataView>}
interface Service {getCharacteristic(uuid:string):Promise<Characteristic>}
interface Server {connected:boolean;connect():Promise<Server>;disconnect():void;getPrimaryService(uuid:string):Promise<Service>}
interface Device extends EventTarget {gatt?:Server}
interface Bluetooth {requestDevice(options:{acceptAllDevices:true;optionalServices:string[]}):Promise<Device>}
export type BluetoothState='disconnected'|'connecting'|'connected';
export function bluetoothAvailable(){return window.isSecureContext&&Boolean((navigator as Navigator&{bluetooth?:Bluetooth}).bluetooth);}

export class WatchBluetooth {
  private device?:Device;private heart?:Characteristic;private battery?:Characteristic;private generation=0;
  private data:WatchData={source:'bluetooth'};
  constructor(private onData:(data:WatchData|undefined)=>void,private onState:(state:BluetoothState)=>void,private onError:(message:string)=>void){}
  private emit(){this.onData({...this.data,heartSamples:[...(this.data.heartSamples||[])]});}
  private heartChanged=(event:Event)=>{
    const value=(event.target as Characteristic).value;if(!value)return;
    try {const reading=decodeHeartRate(value),at=new Date().toISOString();
      this.data={...this.data,heartRate:reading.bpm,heartRateAt:at,
        heartSamples:[...(this.data.heartSamples||[]),{at,bpm:reading.bpm}].slice(-60)};
      this.onError('');this.emit();
    } catch(error){this.data={...this.data,heartRate:undefined,heartRateAt:undefined};this.emit();
      this.onError(error instanceof Error?error.message:'Invalid heart-rate notification.');}
  };
  private batteryChanged=(event:Event)=>{const value=(event.target as Characteristic).value;if(value)this.readBattery(value);};
  private readBattery(value:DataView){if(value.byteLength!==1||value.getUint8(0)>100)return;
    this.data={...this.data,battery:value.getUint8(0),batteryAt:new Date().toISOString()};this.emit();}
  private lost=()=>{this.disconnect();this.onError('Bluetooth disconnected. Reconnect the watch to resume readings.');};
  async connect(){
    this.disconnect();const generation=this.generation;
    if(!bluetoothAvailable()){this.onError('Use Chrome or Edge on this laptop, or Chrome on Android, with Bluetooth enabled and HTTPS or localhost.');return;}
    this.onState('connecting');this.onError('');
    try {
      const bluetooth=(navigator as Navigator&{bluetooth:Bluetooth}).bluetooth;
      // The browser chooser is opened only by the explicit Connect Bluetooth click.
      const device=await bluetooth.requestDevice({acceptAllDevices:true,optionalServices:['heart_rate','battery_service']});
      if(generation!==this.generation)return;
      this.device=device;device.addEventListener('gattserverdisconnected',this.lost);
      if(!device.gatt)throw new Error('unavailable');
      const server=await device.gatt.connect();if(generation!==this.generation){server.disconnect();return;}
      let heart:Characteristic;
      try {heart=await (await server.getPrimaryService('heart_rate')).getCharacteristic('heart_rate_measurement');}
      catch {throw new Error('missing_standard_heart_rate');}
      if(generation!==this.generation)return;
      if(!heart.properties.notify&&!heart.properties.indicate)throw new Error('missing_standard_heart_rate');
      this.heart=heart;heart.addEventListener('characteristicvaluechanged',this.heartChanged);
      await heart.startNotifications();if(generation!==this.generation)return;
      this.onState('connected');this.emit();
      try {const battery=await (await server.getPrimaryService('battery_service')).getCharacteristic('battery_level');
        if(generation!==this.generation)return;this.battery=battery;
        if(battery.properties.notify||battery.properties.indicate){battery.addEventListener('characteristicvaluechanged',this.batteryChanged);await battery.startNotifications();}
        if(generation===this.generation&&battery.properties.read){const value=await battery.readValue();if(generation===this.generation)this.readBattery(value);}
      } catch { /* Battery is optional; absent battery never becomes an invented value. */ }
    } catch(error){if(generation!==this.generation)return;this.disconnect();
      this.onError(error instanceof Error&&error.message==='missing_standard_heart_rate'
        ?'This device did not expose standard Heart Rate (0x180D / 0x2A37). An authorized vendor bridge is required; unknown bytes are not decoded.'
        :error instanceof Error&&error.name==='NotFoundError'?'No watch selected. Choose your watch to connect.'
        :'Bluetooth could not connect. Disconnect nRF Connect/NoiseFit temporarily, keep the watch nearby, and try again.');}
  }
  disconnect(){
    this.generation++;
    this.heart?.removeEventListener('characteristicvaluechanged',this.heartChanged);
    this.battery?.removeEventListener('characteristicvaluechanged',this.batteryChanged);
    for(const characteristic of [this.heart,this.battery])if(characteristic)void characteristic.stopNotifications().catch(()=>{});
    this.device?.removeEventListener('gattserverdisconnected',this.lost);this.device?.gatt?.disconnect();
    this.device=undefined;this.heart=undefined;this.battery=undefined;this.data={source:'bluetooth'};
    this.onData(undefined);this.onState('disconnected');
  }
}
