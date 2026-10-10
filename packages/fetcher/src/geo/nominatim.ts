import { z } from "zod";
import type { JsonCache } from "../lib/cache.ts";
import type { HttpClient } from "../lib/http.ts";

/**
 * OpenStreetMap's geocoder, for venues OSM does not know as cinemas (school halls etc.).
 * Usage policy: at most 1 request per second, an identifying User-Agent, cache results.
 * https://operations.osmfoundation.org/policies/nominatim/
 */
export const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";

const CACHE_MAX_AGE_MS = 30 * 24 * 3_600_000;

const RawPlace = z.looseObject({
  osm_type: z.string().optional(),
  osm_id: z.number().optional(),
  lat: z.string(),
  lon: z.string(),
  display_name: z.string(),
});

export type Place = { lat: number; lon: number; label: string; url?: string };

/** Pure: Nominatim jsonv2 -> places. */
export const parseNominatim = (raw: unknown): Place[] =>
  z
    .array(RawPlace)
    .parse(raw)
    .map((p) => ({
      lat: Number(p.lat),
      lon: Number(p.lon),
      label: p.display_name,
      ...(p.osm_type &&
        p.osm_id && { url: `https://www.openstreetmap.org/${p.osm_type}/${p.osm_id}` }),
    }));

export const geocode = async (
  http: HttpClient,
  cache: JsonCache,
  address: string,
): Promise<Place[]> =>
  parseNominatim(
    await cache.get(`nominatim:${address}`, CACHE_MAX_AGE_MS, () =>
      http.getJson(NOMINATIM_URL, { q: address, format: "jsonv2", countrycodes: "fi", limit: 3 }),
    ),
  );
