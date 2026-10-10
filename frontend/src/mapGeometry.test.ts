import {describe, expect, it} from 'vitest';
import {historical} from './data';
import {locationInput, routePath} from './mapGeometry';

describe('geographic journey inputs', () => {
  it('projects GeoJSON longitude/latitude to Google named coordinates', () => {
    const route = historical.routes[0]; const path = routePath(route);
    expect(path[0]).toEqual({lng:route.geometry.coordinates[0][0], lat:route.geometry.coordinates[0][1]});
    expect(path.length).toBeGreaterThan(10);
  });
  it('rejects a malformed path instead of connecting across missing points', () => {
    const route = structuredClone(historical.routes[0]); route.geometry.coordinates[1] = [77, NaN];
    expect(routePath(route)).toEqual([]);
  });
  it('accepts place text and latitude/longitude map picks', () => {
    expect(locationInput(' India Gate, Delhi ')).toBe('India Gate, Delhi');
    expect(locationInput('28.6129, 77.2295')).toEqual({latitude:28.6129, longitude:77.2295});
    expect(() => locationInput('128.6, 77.2')).toThrow('Coordinates');
  });
});
