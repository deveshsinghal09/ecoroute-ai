import {describe,it,expect} from 'vitest';
import {trainPose} from './trainMotion';
describe('decorative rail movement',()=>{
 it('maintains half-loop spacing without overtaking',()=>{
  for(let t=0;t<136;t+=.25){const a=trainPose(t,0),b=trainPose(t,1);expect(Math.abs(a.x-b.x)).toBeCloseTo(1350,6);expect(Number.isFinite(a.angle)).toBe(true);}
 });
 it('stays on the traced middle rail at a known point',()=>{
  const p=trainPose(((600+500)/2700-.43+1)*68,0);expect(p.x).toBeCloseTo(600);expect(p.y-32*p.scale).toBeCloseTo(592);
 });
});
