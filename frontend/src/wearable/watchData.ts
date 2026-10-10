export type WatchData = {health:number;heartRate:number;steps:number;calories:number;sleep:number;sleepDuration:string;oxygen:number;battery:number;activity:number;hydration:number};
export const watchPages = ['Home','Heart','Activity','Sleep','Wellness','Notifications','Settings'] as const;
export type WatchPage = typeof watchPages[number];
export type WatchSettings = {accent:string;brightness:number;motion:boolean;previewAlerts:boolean};
export function pageAfter(page:number, direction:number){return (page+direction+watchPages.length)%watchPages.length;}
export function pageSummary(page:WatchPage,d?:WatchData){
  if(!d)return page==='Settings'?'Appearance settings only. Device consent and notifications are unchanged.':'Watch not connected. No readings available.';
  switch(page){
    case 'Home':return `Health ${d.health}/100 · ${d.heartRate} BPM · ${d.steps.toLocaleString('en-US')} steps · ${d.calories} kcal · Sleep ${d.sleep}/100 · Oxygen ${d.oxygen}% · Battery ${d.battery}%`;
    case 'Heart':return `${d.heartRate} BPM · Illustrative pulse graph, not measured`;
    case 'Activity':return `${d.steps.toLocaleString('en-US')} steps · ${d.calories} kcal · Movement ${d.activity}%`;
    case 'Sleep':return `Sleep ${d.sleep}/100 · ${d.sleepDuration} · Sample quality: restful`;
    case 'Wellness':return `Blood oxygen ${d.oxygen}% · Hydration ${d.hydration}% · Sample data only`;
    case 'Notifications':return 'Preview messages only. No notifications sent.';
    case 'Settings':return 'Preview appearance only. These settings do not change device consent or real notifications.';
  }
}
