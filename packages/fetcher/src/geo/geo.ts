import { z } from "zod";

/** Mainland Finland and Åland, generously rounded. Catches swapped lat/lon. */
export const FINLAND_BOUNDS = { minLat: 59.5, maxLat: 70.2, minLon: 19.0, maxLon: 31.6 };

/** A point in Finland (WGS 84). */
export const FinnishGeo = z.object({
  lat: z.number().min(FINLAND_BOUNDS.minLat).max(FINLAND_BOUNDS.maxLat),
  lon: z.number().min(FINLAND_BOUNDS.minLon).max(FINLAND_BOUNDS.maxLon),
});
export type FinnishGeo = z.infer<typeof FinnishGeo>;

/**
 * Where a hand-entered coordinate came from. Never Google Maps: its terms forbid storing
 * coordinates taken from it.
 * - `osm:node/123` (or way/relation): an OpenStreetMap object (ODbL, attribution required)
 * - `nominatim`: OSM's geocoder, from the address
 * - `nls`: National Land Survey of Finland geocoding (CC BY 4.0), from the address
 * - `manual`: placed by hand on the OSM map, e.g. a hall OSM does not know as a cinema
 */
export const GeoSource = z
  .string()
  .regex(
    /^(osm:(node|way|relation)\/\d+|nominatim|nls|manual)$/,
    "osm:<type>/<id>, nominatim, nls or manual",
  );

const EARTH_RADIUS_M = 6_371_000;
const rad = (deg: number) => (deg * Math.PI) / 180;

/** Great-circle (haversine) distance in metres. */
export const distanceMeters = (
  a: { lat: number; lon: number },
  b: { lat: number; lon: number },
): number => {
  const h =
    Math.sin(rad(b.lat - a.lat) / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lon - a.lon) / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
};
