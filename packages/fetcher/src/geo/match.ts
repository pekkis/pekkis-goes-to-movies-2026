import { normalizeTitle } from "../matching/titles.ts";
import { distanceMeters } from "./geo.ts";
import type { OsmCinema } from "./osm.ts";

export type LocatableVenue = {
  id: string;
  name: string;
  shortName?: string | undefined;
  city: string;
  geo?: { lat: number; lon: number } | undefined;
};

export type Candidate = { cinema: OsmCinema; nameScore: number; sameCity: boolean };

const trigrams = (s: string): Set<string> => {
  const padded = `  ${normalizeTitle(s)} `;
  const out = new Set<string>();
  for (let i = 0; i < padded.length - 2; i++) out.add(padded.slice(i, i + 3));
  return out;
};

/** Trigram Jaccard similarity, 0..1 (like pg_trgm's similarity). */
export const nameSimilarity = (a: string, b: string): number => {
  const x = trigrams(a);
  const y = trigrams(b);
  let shared = 0;
  for (const t of x) if (y.has(t)) shared++;
  return shared / (x.size + y.size - shared || 1);
};

const MIN_NAME_SCORE = 0.3;
/** Same `addr:city` helps, but must not outrank a clearly matching name. */
const SAME_CITY_BONUS = 0.3;

/**
 * Pure: OSM cinemas that may be this venue, best first. A candidate needs a similar name
 * or the same `addr:city`; many OSM cinemas lack the city tag, so names carry most weight.
 * Suggestions only: a human checks each on the map before it goes into config.
 */
export const candidatesFor = (
  venue: LocatableVenue,
  cinemas: OsmCinema[],
  limit = 3,
): Candidate[] =>
  cinemas
    .map((cinema) => {
      const names = [venue.name, venue.shortName, `${venue.name} ${venue.city}`].filter(
        (n): n is string => Boolean(n),
      );
      const nameScore = cinema.name
        ? Math.max(...names.map((n) => nameSimilarity(n, cinema.name!)))
        : 0;
      const sameCity =
        cinema.city !== undefined && normalizeTitle(cinema.city) === normalizeTitle(venue.city);
      return { cinema, nameScore, sameCity };
    })
    .filter((c) => c.nameScore >= MIN_NAME_SCORE || c.sameCity)
    .sort(
      (a, b) =>
        b.nameScore +
        (b.sameCity ? SAME_CITY_BONUS : 0) -
        (a.nameScore + (a.sameCity ? SAME_CITY_BONUS : 0)),
    )
    .slice(0, limit);

export type Suspect = { venue: LocatableVenue; nearest?: OsmCinema; distance: number };

/**
 * Pure: venues with coordinates farther than `maxMeters` from every OSM cinema. Either our
 * point is off, or OSM lacks the cinema (worth adding to OSM, too).
 */
export const suspiciousCoordinates = (
  venues: LocatableVenue[],
  cinemas: OsmCinema[],
  maxMeters = 300,
): Suspect[] =>
  venues.flatMap((venue) => {
    if (!venue.geo) return [];
    let nearest: OsmCinema | undefined;
    let distance = Infinity;
    for (const cinema of cinemas) {
      const d = distanceMeters(venue.geo, cinema);
      if (d < distance) [nearest, distance] = [cinema, d];
    }
    return distance > maxMeters ? [{ venue, ...(nearest && { nearest }), distance }] : [];
  });

/** Ready to paste into sites.ts. Six decimals is about 0.1 m. */
export const geoSnippet = (point: { lat: number; lon: number }, source: string): string =>
  `geo: { lat: ${Number(point.lat.toFixed(6))}, lon: ${Number(point.lon.toFixed(6))} }, geoSource: "${source}",`;
