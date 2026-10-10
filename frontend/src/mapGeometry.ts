import type {Route} from './data';

export function routePath(route:Route):{lat:number; lng:number}[] {
  const points = route.geometry?.coordinates;
  if (route.geometry?.type !== 'LineString' || !Array.isArray(points) || points.length < 2) return [];
  if (points.some(point => !Array.isArray(point) || point.length < 2 ||
    !Number.isFinite(point[0]) || !Number.isFinite(point[1]) || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90)) return [];
  return points.map(([lng, lat]) => ({lat, lng}));
}

// Map picks display latitude, longitude; the backend receives explicit named fields.
export function locationInput(value:string):string|{latitude:number; longitude:number} {
  const match = /^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/.exec(value);
  if (!match) return value.trim();
  const latitude = Number(match[1]), longitude = Number(match[2]);
  if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) throw new Error('Coordinates must be latitude, longitude within valid geographic bounds.');
  return {latitude, longitude};
}
