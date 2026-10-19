/**
 * Distances on the map, shared by every package (the website's search, the MCP server).
 * Plain math on WGS 84 coordinates; good to a few metres at Finland's latitudes.
 */
export type Point = { lat: number; lon: number };

const EARTH_RADIUS_KM = 6371;
const RAD = Math.PI / 180;

/** Great-circle distance in kilometres (haversine). */
export const distanceKm = (a: Point, b: Point): number => {
  const dLat = (b.lat - a.lat) * RAD;
  const dLon = (b.lon - a.lon) * RAD;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a.lat * RAD) * Math.cos(b.lat * RAD) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
};

/**
 * The box around a point that holds every place within `km`: `[minLon, minLat, maxLon,
 * maxLat]`, as the API's `bbox` takes it. Its corners reach further than `km`, so callers
 * filter by `distanceKm` afterwards.
 */
export const bboxAround = (center: Point, km: number): [number, number, number, number] => {
  const dLat = km / (EARTH_RADIUS_KM * RAD);
  const dLon = dLat / Math.cos(center.lat * RAD);
  return [center.lon - dLon, center.lat - dLat, center.lon + dLon, center.lat + dLat];
};
