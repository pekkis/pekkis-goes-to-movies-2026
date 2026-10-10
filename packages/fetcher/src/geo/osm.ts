import { z } from "zod";
import type { JsonCache } from "../lib/cache.ts";
import type { HttpClient } from "../lib/http.ts";

/**
 * Every cinema in Finland from OpenStreetMap, in one Overpass query.
 * Data © OpenStreetMap contributors, ODbL: attribution required wherever it is shown.
 * Overpass is a shared community service: one query, cached for a week.
 */
export const OVERPASS_URL = "https://overpass-api.de/api/interpreter";

export const OVERPASS_QUERY = `[out:json][timeout:90];
area["ISO3166-1"="FI"][admin_level=2]->.fi;
nwr["amenity"="cinema"](area.fi);
out center tags;`;

const CACHE_MAX_AGE_MS = 7 * 24 * 3_600_000;

const RawElement = z.looseObject({
  type: z.enum(["node", "way", "relation"]),
  id: z.number(),
  lat: z.number().optional(),
  lon: z.number().optional(),
  center: z.object({ lat: z.number(), lon: z.number() }).optional(),
  tags: z.record(z.string(), z.string()).optional(),
});

export const OverpassResponse = z.looseObject({ elements: z.array(z.unknown()) });

export type OsmCinema = {
  /** "osm:node/123", usable as a geoSource as-is. */
  ref: string;
  url: string;
  name?: string;
  lat: number;
  lon: number;
  city?: string;
  address?: string;
  postalCode?: string;
};

/** Pure: Overpass JSON -> cinemas. Elements without a position are skipped. */
export const parseOverpass = (raw: unknown): OsmCinema[] =>
  OverpassResponse.parse(raw).elements.flatMap((item) => {
    const parsed = RawElement.safeParse(item);
    if (!parsed.success) return [];
    const e = parsed.data;
    const lat = e.lat ?? e.center?.lat;
    const lon = e.lon ?? e.center?.lon;
    if (lat === undefined || lon === undefined) return [];
    const t = e.tags ?? {};
    const street = [t["addr:street"], t["addr:housenumber"]].filter(Boolean).join(" ");
    return [
      {
        ref: `osm:${e.type}/${e.id}`,
        url: `https://www.openstreetmap.org/${e.type}/${e.id}`,
        lat,
        lon,
        ...(t["name"] && { name: t["name"] }),
        ...(t["addr:city"] && { city: t["addr:city"] }),
        ...(street && { address: street }),
        ...(t["addr:postcode"] && { postalCode: t["addr:postcode"] }),
      },
    ];
  });

export const fetchOsmCinemas = async (http: HttpClient, cache: JsonCache): Promise<OsmCinema[]> =>
  parseOverpass(
    await cache.get(`overpass:${OVERPASS_QUERY}`, CACHE_MAX_AGE_MS, () =>
      http.getJson(OVERPASS_URL, { data: OVERPASS_QUERY }),
    ),
  );
