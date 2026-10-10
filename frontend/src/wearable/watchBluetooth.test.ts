import {describe,it,expect} from 'vitest';
import {decodeHeartRate} from './watchBluetooth';
import {watchDataFromLatest,pageSummary} from './watchData';
const packet=(bytes:number[])=>new DataView(Uint8Array.from(bytes).buffer);

describe('documented Bluetooth heart-rate packets',()=>{
 it('reads unsigned 8-bit BPM with unsupported contact status',()=>{
  expect(decodeHeartRate(packet([0,76]))).toEqual({bpm:76,contact:'unsupported',rrSeconds:[]});
 });
 it('reads little-endian 16-bit BPM, contact, energy and RR units',()=>{
  expect(decodeHeartRate(packet([31,200,0,10,0,0,4,0,2]))).toEqual({bpm:200,contact:'detected',rrSeconds:[1,.5]});
 });
 it.each([[],[0],[1,76],[8,76,0],[16,76],[16,76,0],[0,10],[0,251],[0,76,2],
  [2,1,...Array(16).fill(0)]].map(bytes=>({bytes})))('rejects incomplete/out-of-range/unknown bytes $bytes',({bytes})=>{
  expect(()=>decodeHeartRate(packet(bytes))).toThrow();
 });
 it('rejects explicitly reported missing skin contact',()=>{
  expect(()=>decodeHeartRate(packet([4,76]))).toThrow('skin contact');
 });
});
describe('partial real data for the watch display',()=>{
 const timestamp=new Date().toISOString();
 it('maps only available non-synthetic fields and leaves other metrics absent',()=>{
  const data=watchDataFromLatest({measurement:{timestamp,heart_rate_bpm:76,steps:8420,steps_semantics:'daily_total',provenance:{synthetic:false}}});
  expect(data).toEqual({source:'backend',reportedAt:timestamp,heartRate:76,heartRateAt:timestamp,steps:8420});
  expect(pageSummary('Wellness',data)).toContain('Blood oxygen Unavailable');
  expect(pageSummary('Home',data)).toContain('Health score unavailable');
 });
 it('does not label interval step counts as daily totals',()=>{
  expect(watchDataFromLatest({measurement:{timestamp,steps:12,steps_semantics:'interval_count',provenance:{synthetic:false}}})).toBeUndefined();
 });
 it.each([{timestamp:'invalid',heart_rate_bpm:76,provenance:{synthetic:false}},
  {timestamp:'2026-10-11T12:00:00',heart_rate_bpm:76,provenance:{synthetic:false}},
  {timestamp,heart_rate_bpm:76,provenance:{synthetic:true}},
  {timestamp,heart_rate_bpm:300,provenance:{synthetic:false}}])('rejects unsupported source data',measurement=>{
  expect(watchDataFromLatest({measurement})).toBeUndefined();
 });
});
