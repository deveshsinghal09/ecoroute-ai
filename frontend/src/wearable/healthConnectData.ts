import type {WatchData} from './watchData';

export type HealthMetricKey='heart_rate'|'blood_pressure'|'oxygen_saturation'|'steps'|'sleep'|'calories_burned'|'resting_heart_rate'|'respiratory_rate';
export type HealthMetric={value:number|{systolic:number;diastolic:number}|null;unit:string;status:'available'|'unavailable'|'partial';timestamp:string|null;source_applications:string[];resolution:string|null;stale:boolean;warnings:string[]};
export type HealthSummary={status:'available'|'empty';selected_date:string;timezone:string;fetched_at:string;payload_generated_at:string|null;last_synchronization_at:string|null;retrieval:'fresh'|'phone_cache';metrics:Record<HealthMetricKey,HealthMetric>;calorie_basis:'total'|'active'|null;warnings:string[];skipped_records:number;medical_assessment:false};
export const metricLabels:Record<HealthMetricKey,string>={heart_rate:'Heart rate',blood_pressure:'Blood pressure',oxygen_saturation:'SpO₂',steps:'Daily steps',sleep:'Sleep duration',calories_burned:'Calories burned',resting_heart_rate:'Resting heart rate',respiratory_rate:'Respiratory rate'};
export function localDateKey(value=new Date()){return `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;}
export function metricText(key:HealthMetricKey,metric?:HealthMetric){
 if(!metric||metric.status!=='available'||metric.value===null)return 'No data available';
 if(key==='blood_pressure'&&typeof metric.value==='object'){
  const {systolic,diastolic}=metric.value;return Number.isFinite(systolic)&&Number.isFinite(diastolic)?`${systolic} / ${diastolic}`:'No data available';
 }
 if(typeof metric.value!=='number'||!Number.isFinite(metric.value))return 'No data available';
 if(key==='sleep'){const minutes=Math.round(metric.value/60);return `${Math.floor(minutes/60)}h ${minutes%60}m`;}
 return metric.value.toLocaleString(undefined,{maximumFractionDigits:key==='steps'?0:1});
}
export function watchDataFromHealthConnect(summary:HealthSummary):WatchData{
 const value=(key:HealthMetricKey)=>{const metric=summary.metrics[key];return metric?.status==='available'&&typeof metric.value==='number'&&Number.isFinite(metric.value)?metric.value:undefined;};
 return {source:'health_connect',reportedAt:summary.fetched_at,selectedDate:summary.selected_date,
  heartRate:value('heart_rate'),heartRateAt:summary.metrics.heart_rate.timestamp||undefined,
  steps:value('steps'),calories:value('calories_burned'),oxygen:value('oxygen_saturation'),
  sleepDuration:value('sleep')===undefined?undefined:metricText('sleep',summary.metrics.sleep)};
}
export function metricNote(metric?:HealthMetric){
 if(!metric)return '';
 if(metric.warnings.some(w=>w.startsWith('unfinished_or_projected')))return 'Unfinished interval; not an actual daily total.';
 if(metric.warnings.includes('overlapping_intervals_total_unavailable'))return 'Overlapping records; a reliable total is unavailable.';
 if(metric.warnings.includes('cross_midnight_counts_cannot_be_split_without_samples'))return 'Record crosses midnight; no daily total inferred.';
 if(metric.warnings.includes('conflicting_latest_records'))return 'Conflicting measurements at the same time.';
 if(metric.warnings.includes('invalid_records_prevent_daily_total'))return 'Invalid records prevent a reliable daily total.';
 if(metric.warnings.some(w=>w.startsWith('cached_')))return 'Cached records are incomplete for this daily total.';
 if(metric.status!=='available')return '';
 const source=metric.source_applications.length?metric.source_applications.join(', '):'Source app not reported';
 return `${source}${metric.resolution==='bucket_average'?' · averaged reading':''}${metric.stale?' · older record':''}${metric.resolution==='recorded_interval_sum'?' · sum of available records; day coverage unverified':''}${metric.resolution==='session_interval_union'?' · session duration includes any awake time':''}`;
}
