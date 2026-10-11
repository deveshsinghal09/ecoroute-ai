import {expect,it} from 'vitest';
import {airQuality,datasetSummary} from './airQuality';
import {historical} from './data';

it('asks for a route without presenting a missing pollution reading',()=>{
 const result=airQuality();expect(result.dataTitle).toBe('Choose a route first');
 expect(result.description).toContain('Compare your start');expect(result.concentration).toBeNull();
 expect(result.coverageText).toBe('Not checked');
});
it('checks actual saved route arithmetic including floating-point full coverage',()=>{
 for(const route of historical.routes){
  const result=airQuality(route,false);
  expect(result.concentration).toBeCloseTo(69.2);expect(result.coverageText).toBe('Whole journey');
  expect(result.names).toEqual(['Open-Meteo / CAMS']);expect(result.resolution).toEqual([45]);
  expect(result.type).toBe('Saved forecast');expect(result.checks[0].ok).toBe(true);
  expect(result.checks[1].ok).toBe(true);expect(result.checks[2].detail).toContain('not current conditions');
 }
});
it('does not create an average or clean-air claim when data is missing',()=>{
 const route={...historical.routes[0],estimated_pm25_exposure_ug_h_m3:null,pm25_coverage_fraction:0,segments:[]};
 const result=airQuality(route);
 expect(result.concentration).toBeNull();expect(result.dataTitle).toBe('Air estimate unavailable');
 expect(result.description).toContain('does not mean clean air');expect(result.checks[0].ok).toBe(false);
});
it('keeps partial coverage visibly partial and a zero concentration valid',()=>{
 const route=historical.routes[0];
 expect(airQuality({...route,pm25_coverage_fraction:.5}).coverageText).toBe('50.0% of travel time');
 expect(airQuality({...route,pm25_coverage_fraction:.5}).concentration).toBeNull();
 expect(airQuality({...route,estimated_pm25_exposure_ug_h_m3:0}).concentration).toBe(0);
});
it('flags inconsistent arithmetic and rejected or impossible segment readings',()=>{
 const route=historical.routes[0];
 expect(airQuality({...route,estimated_pm25_exposure_ug_h_m3:999}).checks[1].ok).toBe(false);
 for(const changes of [{value_ug_m3:-1},{value_ug_m3:NaN},{quality_flags:['rejected']}]){
  const segments=route.segments.map(s=>({...s,pollutants:{...s.pollutants,pm25:{...s.pollutants.pm25,...changes}}}));
  const result=airQuality({...route,segments});expect(result.checks[0].ok).toBe(false);expect(result.checks[1].ok).toBe(false);
 }
});
it('checks forecast collection age without calling a saved forecast live',()=>{
 const route=historical.routes[0];
 expect(airQuality(route,true,Date.parse('2026-10-12T00:00:00Z')).outdated).toBe(true);
 expect(airQuality(route,false,Date.parse('2026-10-12T00:00:00Z')).outdated).toBe(false);
 expect(airQuality(route,true,Date.parse('2026-10-08T00:00:00Z')).checks[2].detail).toContain('future');
});
it('separates station measurements from area-wide forecasts',()=>{
 const route=historical.routes[0];
 const segments=route.segments.map(s=>({...s,pollutants:{...s.pollutants,pm25:{...s.pollutants.pm25,status:'observed',source:'openaq',resolution_km:null}}}));
 const result=airQuality({...route,segments});expect(result.type).toBe('Nearby station readings');expect(result.names).toEqual(['OpenAQ']);expect(result.resolution).toEqual([]);
});
it('summarizes collection reports without dumping keys or claiming route coverage',()=>{
 const text=datasetSummary({reports:[{records:192,missing_or_rejected:2,flagged:1,raw_key:'PRIVATE_PATH',provider_text:'UNTRUSTED'}]});
 expect(text).toContain('192 readings');expect(text).toContain('2 readings were missing');expect(text).toContain('not your selected route');
 expect(text).not.toMatch(/PRIVATE|UNTRUSTED/);
 expect(datasetSummary({reports:[]})).toContain('No collection reports');
});
it('rejects malformed collection responses rather than displaying arbitrary content',()=>{
 for(const value of [null,{}, {reports:'secret'}, {reports:[{records:-1}]},{reports:[{records:'192'}]}])expect(()=>datasetSummary(value)).toThrow('unexpected result');
});
