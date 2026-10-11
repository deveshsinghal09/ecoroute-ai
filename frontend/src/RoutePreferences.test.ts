import {describe,it,expect} from 'vitest';
import {compatiblePreferences,defaultPreferences} from './RoutePreferences';
describe('Mode-specific route preferences',()=>{
  it('never sends driving avoidance or climbing options on a walking request',()=>{
    const value=compatiblePreferences({...defaultPreferences,avoid_tolls:true,avoid_highways:true,avoid_steps:true,terrain_weight:.2},'walking');
    expect(value.avoid_tolls).toBe(false);expect(value.avoid_highways).toBe(false);expect(value.avoid_steps).toBe(false);expect(value.terrain_weight).toBe(0);
  });
  it('preserves cycling climbing and weather settings without relabeling modes',()=>{
    const value=compatiblePreferences({...defaultPreferences,terrain_weight:.2,weather_weight:.2,avoid_steps:true},'cycling');
    expect(value.terrain_weight).toBe(.2);expect(value.weather_weight).toBe(.2);expect(value.avoid_steps).toBe(true);
    expect(value.exposure_weight+value.weather_weight+value.terrain_weight).toBeLessThanOrEqual(1);
  });
});

it('pure objectives do not request unused weather or climbing data, but keep driving avoidance',()=>{
 const settings={...defaultPreferences,weather_weight:.2,terrain_weight:.2,avoid_tolls:true};
 const fastest=compatiblePreferences(settings,'driving','fastest');
 expect(fastest.exposure_weight).toBe(0);expect(fastest.weather_weight).toBe(0);expect(fastest.terrain_weight).toBe(0);expect(fastest.avoid_tolls).toBe(true);
 const pollution=compatiblePreferences(settings,'cycling','lowest_exposure');
 expect(pollution.exposure_weight).toBe(1);expect(pollution.weather_weight).toBe(0);expect(pollution.terrain_weight).toBe(0);
 expect(settings.weather_weight).toBe(.2); // Original balanced settings remain available when switching back.
});
