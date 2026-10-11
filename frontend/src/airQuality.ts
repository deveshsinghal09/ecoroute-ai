import {number,type Route} from './data';

const finite=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value);
const nonnegative=(value:unknown):value is number=>finite(value)&&value>=0;
const sourceNames=new Map([['open_meteo','Open-Meteo / CAMS'],['openaq','OpenAQ'],['station_prediction','EcoRoute station model']]);
export function airQuality(route?:Route,live=true,now=Date.now()) {
  const segments=route?.segments||[];
  const usable=segments.filter(s=>nonnegative(s.pollutants.pm25?.value_ug_m3)&&finite(s.duration_s)&&s.duration_s>0&&!s.pollutants.pm25.quality_flags?.length);
  const coveredSeconds=usable.reduce((sum,s)=>sum+s.duration_s,0);
  const coverage=route&&finite(route.pm25_coverage_fraction)?Math.min(1,Math.max(0,route.pm25_coverage_fraction)):null;
  const complete=!!route&&coverage!==null&&Math.abs(coverage-1)<=1e-9&&finite(route.duration_s)&&route.duration_s>0;
  const average=complete&&nonnegative(route?.estimated_pm25_exposure_ug_h_m3)?route.estimated_pm25_exposure_ug_h_m3/(route.duration_s/3600):null;
  const concentration=finite(average)?average:null;
  const readings=usable.map(s=>s.pollutants.pm25);
  const names=[...new Set(readings.map(r=>sourceNames.get(r.source||'')||'Source not identified'))];
  const kinds=new Set(readings.map(r=>r.status));
  const type=!live?'Saved forecast':!readings.length?'Not available':kinds.size===1&&kinds.has('observed')?'Nearby station readings':kinds.size===1&&kinds.has('station_prediction')?'Station prediction':[...kinds].every(k=>k==='modeled'||k==='forecast')?'Area-wide forecast':'Mixed air-quality sources';
  const resolution=[...new Set(readings.map(r=>r.resolution_km).filter((v):v is number=>finite(v)&&v>0))];
  const collected=readings.map(r=>Date.parse(r.collected_at||'')).filter(Number.isFinite);
  const oldest=collected.length?Math.min(...collected):null;
  const outdated=live&&readings.some(r=>r.source==='open_meteo'&&Number.isFinite(Date.parse(r.collected_at||''))&&now-Date.parse(r.collected_at!)>24*3600000);
  const allDownloadTimes=readings.length>0&&collected.length===readings.length;
  const futureDownload=collected.some(stamp=>stamp>now+60000);
  const dataTitle=!route?'Choose a route first':concentration===null?'Air estimate unavailable':'Air along your route';
  const description=!route?'Compare your start and destination in City overview, then select a route to see its air estimate.':concentration===null?'We do not have enough air-quality data for this journey. Compare again, or try another departure time. Missing data does not mean clean air.':'Estimated average amount of tiny particles (PM2.5) in the air during your journey. A lower number means fewer particles; your total exposure also depends on travel time.';
  const partsComplete=complete&&segments.length>0&&usable.length===segments.length&&Math.abs(coveredSeconds-route!.duration_s)<1e-5;
  const total=usable.reduce((sum,s)=>sum+s.pollutants.pm25.value_ug_m3!*s.duration_s/3600,0);
  const arithmetic=partsComplete&&nonnegative(route?.estimated_pm25_exposure_ug_h_m3)&&Math.abs(total-route.estimated_pm25_exposure_ug_h_m3)<=Math.max(1e-6,total*1e-6);
  return {concentration,coverage,type,names,resolution,oldest,outdated,dataTitle,description,
    coverageText:coverage===null?'Not checked':complete?'Whole journey':`${number(coverage*100,1)}% of travel time`,
    checks:[
      {title:'Journey coverage',detail:`${usable.length} of ${segments.length} route sections have usable PM2.5 values.`,ok:partsComplete},
      {title:'Calculation',detail:arithmetic?'The pollution values and travel times match the route’s exposure estimate.':'A complete exposure calculation could not be verified from the returned route sections.',ok:arithmetic},
      {title:'Data age',detail:!live?'This is a saved comparison, not current conditions.':futureDownload?'A download time is in the future and could not be verified.':outdated?'The forecast was downloaded more than 24 hours ago. Compare again to refresh it.':!allDownloadTimes?'Some download times were not supplied.':'Download times are available below. They do not verify when a sensor measured the air.',ok:live&&allDownloadTimes&&!outdated&&!futureDownload},
    ]};
}

export function datasetSummary(value:unknown) {
  if(!value||typeof value!=='object'||!('reports' in value)||!Array.isArray(value.reports))throw new Error('The data check returned an unexpected result. Please try again.');
  if(!value.reports.length)return 'No collection reports are available yet. This does not tell us whether your selected route has air-quality data.';
  const report=value.reports[0];
  if(!report||typeof report!=='object'||!Number.isInteger(report.records)||report.records<0)throw new Error('The data check returned an unexpected result. Please try again.');
  const missing=Number.isInteger(report.missing_or_rejected)&&report.missing_or_rejected>=0?` ${report.missing_or_rejected} readings were missing or rejected.`:'';
  const flagged=Number.isInteger(report.flagged)&&report.flagged>=0?` ${report.flagged} readings have quality warnings.`:'';
  return `The latest collection contains ${report.records} readings.${missing}${flagged} This checks collected datasets, not your selected route.`;
}
