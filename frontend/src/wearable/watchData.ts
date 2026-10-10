export type HeartSample = {at:string;bpm:number};
export type WatchData = {health?:number;heartRate?:number;steps?:number;calories?:number;sleep?:number;sleepDuration?:string;oxygen?:number;battery?:number;activity?:number;hydration?:number;
 source?:'bluetooth'|'backend';reportedAt?:string;heartRateAt?:string;batteryAt?:string;heartSamples?:HeartSample[]};
export const watchPages = ['Home','Heart','Activity','Sleep','Wellness','Notifications','Settings'] as const;
export type WatchPage = typeof watchPages[number];
export type WatchSettings = {accent:string;brightness:number;motion:boolean;previewAlerts:boolean};
export function watchDataFromLatest(input:unknown):WatchData|undefined {
  const result=input as {measurement?:{timestamp?:string;heart_rate_bpm?:number;steps?:number;steps_semantics?:string;provenance?:{synthetic?:boolean}}}|null;
  const row=result?.measurement;
  if(typeof row?.timestamp!=='string'||!/(Z|[+-]\d\d:\d\d)$/.test(row.timestamp)||!Number.isFinite(Date.parse(row.timestamp))||row.provenance?.synthetic!==false)return undefined;
  const heart=typeof row.heart_rate_bpm==='number'&&Number.isInteger(row.heart_rate_bpm)&&row.heart_rate_bpm>=20&&row.heart_rate_bpm<=250?row.heart_rate_bpm:undefined;
  const steps=row.steps_semantics==='daily_total'&&typeof row.steps==='number'&&Number.isInteger(row.steps)&&row.steps>=0&&row.steps<=200000?row.steps:undefined;
  if(heart===undefined&&steps===undefined)return undefined;
  return {source:'backend',reportedAt:row.timestamp,heartRate:heart,heartRateAt:heart===undefined?undefined:row.timestamp,steps};
}
export function pageAfter(page:number, direction:number){return (page+direction+watchPages.length)%watchPages.length;}
export function pageSummary(page:WatchPage,d?:WatchData){
  if(!d)return page==='Settings'?'Appearance settings only. Device consent and notifications are unchanged.':'Watch not connected. No readings available.';
  const value=(n:number|undefined,suffix='')=>n===undefined?'Unavailable':`${n.toLocaleString('en-US')}${suffix}`;
  switch(page){
    case 'Home':return `Heart ${value(d.heartRate,' BPM')} · Steps ${value(d.steps)} · Battery ${value(d.battery,'%')} · Health score unavailable`;
    case 'Heart':return `${value(d.heartRate,' BPM')} · ${d.heartSamples?.length||0} received readings. Trend is heart rate, not ECG.`;
    case 'Activity':return `Steps ${value(d.steps)} · Calories ${value(d.calories,' kcal')} · Movement ${value(d.activity,'%')}`;
    case 'Sleep':return `Sleep ${value(d.sleep,'/100')} · Duration ${d.sleepDuration||'Unavailable'}`;
    case 'Wellness':return `Blood oxygen ${value(d.oxygen,'%')} · Hydration ${value(d.hydration,'%')}`;
    case 'Notifications':return 'No notifications received or sent.';
    case 'Settings':return 'Preview appearance only. These settings do not change device consent or real notifications.';
  }
}
