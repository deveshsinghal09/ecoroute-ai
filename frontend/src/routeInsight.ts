import {number, weightedConcentration, type Comparison, type Route} from './data';

export interface RouteExplanation {explanation:string;mode:string;fallback_reason:string|null}
export function routeSummary(route?:Route,comparison?:Comparison|null) {
  if(!route)return 'Compare routes, then choose one to see what it means for your journey.';
  const fastest=comparison?.routes.find(r=>r.route_id===comparison.recommended_route_ids.fastest);
  let summary=`Your selected route takes about ${number(route.duration_s/60)} minutes and covers ${number(route.distance_m/1000)} km.`;
  if(fastest&&route.route_id===fastest.route_id)summary+=' It is the quickest of the routes compared.';
  else if(fastest&&route.duration_s>fastest.duration_s)summary+=` It takes ${number((route.duration_s-fastest.duration_s)/60)} minutes longer than the quickest option.`;
  if(route.within_detour_limit===false)summary+=' It exceeds your maximum extra travel time.';
  const concentration=weightedConcentration(route);
  if(concentration===null||route.pm25_coverage_fraction<1)summary+=' Some air-quality data is missing, so we cannot reliably compare pollution exposure for the whole journey.';
  else summary+=` The estimated average PM2.5 level is ${number(concentration)} µg/m³. PM2.5 means tiny particles in the air; your exposure also depends on how long you travel.`;
  if(comparison?.spatial_differentiation==='not_resolved_same_model_cell')summary+=' These routes share an area-wide air-quality forecast, so we cannot tell which street has cleaner air.';
  return summary;
}

export function explanationLabel(value?:Pick<RouteExplanation,'mode'|'fallback_reason'>) {
  if(value?.mode==='gemini_arranged_approved_text')return 'Explained with Gemini · based on your route results';
  if(value?.mode==='bedrock_arranged_approved_text')return 'Explained with Bedrock · based on your route results';
  const reason=value?.fallback_reason;
  if(reason==='gemini_provider_quota'||reason==='gemini_request_limit'||reason==='bedrock_request_limit')return 'Route summary · AI request limit reached';
  const unavailable=new Set(['gemini_access_denied','gemini_model_unavailable','gemini_request_rejected','gemini_secret_unavailable','gemini_secret_invalid','gemini_incomplete_or_blocked','gemini_provider_unavailable','gemini_unavailable_or_invalid_output','bedrock_unavailable_or_invalid_output']);
  if(reason&&unavailable.has(reason))return 'Route summary · AI explanation unavailable';
  return 'Route summary · based on your route results';
}
