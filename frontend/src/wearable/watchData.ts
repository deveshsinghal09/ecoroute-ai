// Demo presentation data only. Never submit this object to a telemetry endpoint.
export const watchDemo = Object.freeze({health:87,heartRate:76,steps:8420,calories:324,sleep:92,sleepDuration:'7h 42m',oxygen:98,battery:84,activity:78,hydration:65});
export type WatchData = {health:number;heartRate:number;steps:number;calories:number;sleep:number;sleepDuration:string;oxygen:number;battery:number;activity:number;hydration:number};
export const watchPages = ['Home','Heart','Activity','Sleep','Wellness','Notifications','Settings'] as const;
export type WatchPage = typeof watchPages[number];
export type WatchSettings = {accent:string;brightness:number;motion:boolean;previewAlerts:boolean};
export function pageAfter(page:number, direction:number){return (page+direction+watchPages.length)%watchPages.length;}
export function pageSummary(page:WatchPage,d:WatchData){
  switch(page){
    case 'Home':return `Health ${d.health}/100 · ${d.heartRate} BPM · ${d.steps.toLocaleString('en-US')} steps · ${d.calories} kcal · Sleep ${d.sleep}/100 · Oxygen ${d.oxygen}% · Battery ${d.battery}%`;
    case 'Heart':return `${d.heartRate} BPM · Illustrative pulse graph, not measured`;
    case 'Activity':return `${d.steps.toLocaleString('en-US')} steps · ${d.calories} kcal · Movement ${d.activity}%`;
    case 'Sleep':return `Sleep ${d.sleep}/100 · ${d.sleepDuration} · Demo quality: restful`;
    case 'Wellness':return `Blood oxygen ${d.oxygen}% · Hydration ${d.hydration}% · Demo only`;
    case 'Notifications':return 'Preview messages only. No notifications sent.';
    case 'Settings':return 'Preview appearance only. These settings do not change device consent or real notifications.';
  }
}
