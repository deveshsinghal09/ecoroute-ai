import recording from '../../examples/delhi-recorded-response.json';
export type Position = [number, number];
export interface Route {
  route_id: string; geometry: { type: 'LineString'; coordinates: Position[] };
  duration_s: number; distance_m: number; departure_at: string;
  estimated_pm25_exposure_ug_h_m3: number | null; pm25_coverage_fraction: number;
  relative_exposure_change_percent: number | null; confidence: string;
  source_metadata?: unknown; warnings: string[]; recommendation_reason: string; routing_source: Record<string, unknown>;
  segments: { duration_s: number; pm25_exposure_ug_h_m3: number | null; pollutants: Record<string, {value_ug_m3: number | null; source?: string; reported_at?: string}> }[];
}
export interface Comparison { routes: Route[]; selected_route_id: string; candidate_count: number; recommended_route_ids: Record<string,string|null>; warnings: string[]; spatial_differentiation: string; }
export const historical = recording.response as unknown as Comparison;
export const capturedAt = recording.captured_at;
export function number(value: number | null | undefined, digits = 1) { return value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits); }
export function weightedConcentration(route?: Route) {
  if (!route || route.estimated_pm25_exposure_ug_h_m3 == null || route.duration_s <= 0) return null;
  return route.estimated_pm25_exposure_ug_h_m3 / (route.duration_s / 3600);
}
export function projectRoutes(routes: Route[]) {
  const points = routes.flatMap(r => r.geometry.coordinates);
  if (!points.length) return [];
  const xs = points.map(p => p[0] * Math.cos(28.6 * Math.PI / 180));
  const ys = points.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min(820 / Math.max(maxX-minX, 0.00001), 510 / Math.max(maxY-minY, 0.00001));
  return routes.map(r => r.geometry.coordinates.map(p => [500 + (p[0]*Math.cos(28.6*Math.PI/180)-(minX+maxX)/2)*scale, 330-(p[1]-(minY+maxY)/2)*scale] as Position));
}
