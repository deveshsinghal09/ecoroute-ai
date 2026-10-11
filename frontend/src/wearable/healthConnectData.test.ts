import {describe,expect,it} from 'vitest';
import {localDateKey,metricNote,metricText,watchDataFromHealthConnect,type HealthMetric,type HealthSummary,metricLabels} from './healthConnectData';

const available=(value:HealthMetric['value'],unit='bpm'):HealthMetric=>({value,unit,status:'available',timestamp:'2026-10-11T08:00:00Z',source_applications:[],resolution:'sample',stale:false,warnings:[]});
describe('recorded phone metrics',()=>{
 it('preserves zero, formats pressure/sleep units, and does not render missing or invalid values',()=>{
  expect(metricText('steps',available(0,'count'))).toBe('0');
  expect(metricText('blood_pressure',available({systolic:120,diastolic:80},'mmHg'))).toBe('120 / 80');
  expect(metricText('sleep',available(7*3600+20*60,'s'))).toBe('7h 20m');
  expect(metricText('heart_rate',available(NaN))).toBe('No data available');
  expect(metricText('heart_rate',{...available(76),status:'partial'})).toBe('No data available');
  expect(metricText('steps')).toBe('No data available');
 });
 it('maps only available fields to the watch and never infers health scores or battery',()=>{
  const metrics=Object.fromEntries(Object.keys(metricLabels).map(k=>[k,{...available(null),status:'unavailable'}])) as HealthSummary['metrics'];
  metrics.steps=available(0,'count');metrics.sleep=available(3600,'s');metrics.heart_rate=available(76);
  const result=watchDataFromHealthConnect({metrics,fetched_at:'2026-10-11T08:01:00Z',selected_date:'2026-10-11'} as HealthSummary);
  expect(result).toMatchObject({source:'health_connect',heartRate:76,steps:0,sleepDuration:'1h 0m',selectedDate:'2026-10-11'});
  expect(result.health).toBeUndefined();expect(result.sleep).toBeUndefined();expect(result.battery).toBeUndefined();expect(result.calories).toBeUndefined();
 });
 it('reports overlap, projections, missing provenance and averaged older readings',()=>{
  expect(metricNote({...available(null),warnings:['unfinished_or_projected_intervals_not_actual_daily_total']})).toContain('not an actual daily total');
  expect(metricNote({...available(null),warnings:['overlapping_intervals_total_unavailable']})).toContain('Overlapping');
  expect(metricNote({...available(76),resolution:'bucket_average',stale:true})).toBe('Source app not reported · averaged reading · older record');
 });
 it('uses the local calendar date, rather than UTC slicing',()=>{
  const date=new Date(2026,9,11,0,15);expect(localDateKey(date)).toBe('2026-10-11');
 });
});
