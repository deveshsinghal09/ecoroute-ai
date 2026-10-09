import {describe,it,expect} from 'vitest';
import {trainPose,railAt,stripPose,wheelY,STRIPS,SPRITE_WIDTH} from './trainMotion';
describe('decorative rail movement',()=>{
 it('maintains half-loop spacing without overtaking',()=>{
  for(let t=0;t<136;t+=.25){const a=trainPose(t,0),b=trainPose(t,1);expect(Math.abs(a.x-b.x)).toBeCloseTo(1350,6);expect(Number.isFinite(a.angle)).toBe(true);}
 });
 it('stays on the traced middle rail at a known point',()=>{
  const p=trainPose(((600+500)/2700-.43+1)*68,0);expect(p.x).toBeCloseTo(600);expect(p.y).toBeCloseTo(603);
 });
});

it('anchors every sprite wheel slice to the rail across the entire loop',()=>{
 for(let t=0;t<68;t+=.5)for(let train=0;train<2;train++)for(let strip=0;strip<STRIPS;strip++){
  const p=stripPose(t,train,strip),u=strip*SPRITE_WIDTH/STRIPS;
  expect(p.b*u+p.d*wheelY(u)+p.f).toBeCloseTo(railAt(p.a*u+p.e).y,6);
 }
});
