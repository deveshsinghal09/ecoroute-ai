import {expect,it} from 'vitest';
import {explanationLabel,routeSummary} from './routeInsight';
import {historical,type Route} from './data';

it('names actual AI providers without showing developer setup instructions',()=>{
 expect(explanationLabel({mode:'gemini_arranged_approved_text',fallback_reason:null})).toContain('Gemini');
 expect(explanationLabel({mode:'bedrock_arranged_approved_text',fallback_reason:null})).toContain('Bedrock');
 expect(explanationLabel({mode:'deterministic',fallback_reason:'gemini_request_limit'})).toContain('request limit reached');
 expect(explanationLabel({mode:'deterministic',fallback_reason:'gemini_provider_quota'})).toContain('request limit reached');
 expect(explanationLabel({mode:'deterministic',fallback_reason:'gemini_secret_invalid'})).toContain('AI explanation unavailable');
 expect(explanationLabel({mode:'untrusted markup',fallback_reason:'private-key'})).toBe('Route summary · based on your route results');
 expect(explanationLabel({mode:'deterministic',fallback_reason:'__proto__'})).toBe('Route summary · based on your route results');
});
const route:Route={...historical.routes[0],route_id:'selected',duration_s:900,distance_m:3600,estimated_pm25_exposure_ug_h_m3:12.5,pm25_coverage_fraction:1};
it('explains travel time and particles using existing metrics without a health claim',()=>{
 const text=routeSummary(route);
 expect(text).toContain('15.0 minutes');expect(text).toContain('3.6 km');expect(text).toContain('50.0 µg/m³');
 expect(text).toContain('tiny particles');expect(text).not.toMatch(/safe|medical dose|concentration-time|µg·h|provider candidate/);
});
it('relates a longer selection to the documented quickest route',()=>{
 const fastest={...route,route_id:'fastest',duration_s:600};
 const comparison={...historical,routes:[fastest,route],recommended_route_ids:{fastest:'fastest'},spatial_differentiation:'not_resolved_same_model_cell'};
 expect(routeSummary(route,comparison)).toContain('5.0 minutes longer');
 expect(routeSummary(fastest,comparison)).toContain('quickest of the routes compared');
 expect(routeSummary(route,comparison)).toContain('cannot tell which street has cleaner air');
});
it('does not turn incomplete or missing coverage into an air-quality comparison',()=>{
 for(const value of [{estimated_pm25_exposure_ug_h_m3:null},{pm25_coverage_fraction:.5},{duration_s:0}]){
  const text=routeSummary({...route,...value});expect(text).toContain('data is missing');expect(text).not.toContain('50.0 µg/m³');
 }
});
it('preserves a genuine zero estimate and explains the detour limit',()=>{
 const text=routeSummary({...route,estimated_pm25_exposure_ug_h_m3:0,within_detour_limit:false});
 expect(text).toContain('0.0 µg/m³');expect(text).toContain('maximum extra travel time');
});
it('gives a clear next step without made-up data when no route is selected',()=>{
 expect(routeSummary()).toBe('Compare routes, then choose one to see what it means for your journey.');
});
