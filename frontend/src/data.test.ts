import { describe, expect, it } from 'vitest';
import { historical, number, projectRoutes, weightedConcentration } from './data';
describe('real recorded data presentation',()=>{
  it('does not convert missing values to zero',()=>{expect(number(null)).toBe('—');expect(weightedConcentration()).toBeNull();});
  it('uses hours for concentration-time arithmetic',()=>{const route=historical.routes[0];expect(weightedConcentration(route)!*route.duration_s/3600).toBeCloseTo(route.estimated_pm25_exposure_ug_h_m3!,9);});
  it('preserves every genuine route coordinate in projection',()=>{const projected=projectRoutes(historical.routes);expect(projected).toHaveLength(historical.routes.length);projected.forEach((points,i)=>{expect(points).toHaveLength(historical.routes[i].geometry.coordinates.length);expect(points.every(p=>p.every(Number.isFinite))).toBe(true);});});
});
