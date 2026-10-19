import { bboxAround, distanceKm, type Point } from "@pgtm/model/geo";
import { addDays, isIsoDate } from "@pgtm/model/time";
import { z } from "zod";
import {
  dayScreenings,
  filmDayScreenings,
  listVenues,
  searchFilms,
  type Api,
  type FilmSummary,
  type Screening,
  type Venue,
} from "./api.ts";
import { citiesOf, citySlug, type City } from "./cities.ts";

/**
 * The search page (/fi/haku): a GET form picks the days, the place and maybe a film; the
 * server loads those screenings, and the island narrows them by time of day, venue and film.
 * Bad or missing parameters fall back to defaults, never to an error page.
 */

/** Days the form offers: today and the six after it. */
export const DAYS_AHEAD = 7;
export const RADII_KM = [5, 10, 25, 50, 100] as const;
export const DEFAULT_RADIUS_KM = 25;
/** Films a name search may bring: the best few, and the island can uncheck the rest. */
const FILMS_PER_SEARCH = 3;

/** Finland's bounds, as the API's MCP tools take them. */
const Lat = z.coerce.number().min(59).max(71);
const Lon = z.coerce.number().min(19).max(32);

export type SearchParams = {
  days: string[];
  /** A city's slug, when the place is a city. */
  city?: string;
  /** The browser's location, when the place is "here". */
  here?: Point;
  radiusKm: number;
  /** A film name (path B), two characters or more. */
  film?: string;
};

/** The form's days: today and the next six, in order. */
export const dayOptions = (today: string): string[] =>
  Array.from({ length: DAYS_AHEAD }, (_, i) => addDays(today, i));

export const parseSearchParams = (params: URLSearchParams, today: string): SearchParams => {
  const offered = new Set(dayOptions(today));
  const days = [...new Set(params.getAll("paiva"))]
    .filter((d) => isIsoDate(d) && offered.has(d))
    .toSorted();
  const lat = Lat.safeParse(params.get("lat") ?? undefined);
  const lon = Lon.safeParse(params.get("lon") ?? undefined);
  const radius = Number(params.get("sade"));
  const city = params.get("kaupunki")?.trim();
  const film = params.get("elokuva")?.trim();
  return {
    days: days.length ? days : [today],
    ...(lat.success && lon.success ? { here: { lat: lat.data, lon: lon.data } } : {}),
    ...(city && { city }),
    radiusKm: (RADII_KM as readonly number[]).includes(radius) ? radius : DEFAULT_RADIUS_KM,
    ...(film && film.length >= 2 && { film }),
  };
};

export type Place =
  | { kind: "here"; point: Point }
  | { kind: "city"; name: string; slug: string; point: Point };

/** A city's centre: the mean of its venues' coordinates; none if no venue has any. */
export const cityCentre = (venues: readonly Venue[], name: string): Point | undefined => {
  const points = venues.filter((v) => v.city === name && v.geo).map((v) => v.geo!);
  return points.length
    ? {
        lat: points.reduce((sum, p) => sum + p.lat, 0) / points.length,
        lon: points.reduce((sum, p) => sum + p.lon, 0) / points.length,
      }
    : undefined;
};

/**
 * The place to search around: a chosen city first (picking one after "use my location"
 * means the city), then the browser's location. The location button clears the city.
 */
const placeOf = (params: SearchParams, venues: readonly Venue[]): Place | undefined => {
  const city = params.city && citiesOf(venues).find((c) => c.slug === citySlug(params.city!));
  const point = city && cityCentre(venues, city.name);
  if (city && point) {
    return { kind: "city", name: city.name, slug: city.slug, point };
  }
  return params.here && { kind: "here", point: params.here };
};

export type SearchPage = {
  params: SearchParams;
  dayOptions: string[];
  cities: City[];
  place?: Place;
  /** The films a name search found (path B). */
  films: FilmSummary[];
  /** "start": nothing to search with yet (no place, no film); the form alone is shown. */
  state: "start" | "results";
  screenings: Screening[];
  /** Venue id -> km from the place, for venues in the results. */
  distances: Record<string, number>;
};

const byStart = (a: Screening, b: Screening) =>
  a.startsAt.localeCompare(b.startsAt) || a.id.localeCompare(b.id);

/** Data for /fi/haku. */
export const loadSearchPage = async (
  api: Api,
  query: URLSearchParams,
  today: string,
): Promise<SearchPage> => {
  const params = parseSearchParams(query, today);
  const venues = await listVenues(api);
  const place = placeOf(params, venues);
  const base = {
    params,
    dayOptions: dayOptions(today),
    cities: citiesOf(venues),
    ...(place && { place }),
  };
  if (!place && !params.film) {
    return { ...base, films: [], state: "start", screenings: [], distances: {} };
  }

  const bbox = place
    ? bboxAround(place.point, params.radiusKm)
        .map((n) => n.toFixed(4))
        .join(",")
    : undefined;
  const films = params.film ? await searchFilms(api, params.film, FILMS_PER_SEARCH) : [];
  const loaded = params.film
    ? await Promise.all(
        params.days.flatMap((day) => films.map((f) => filmDayScreenings(api, f.id, day, bbox))),
      )
    : await Promise.all(
        params.days.map(async (day) => (await dayScreenings(api, { bbox: bbox! }, day)).items),
      );

  // The box's corners reach past the radius: keep only what is within it.
  const within = (s: Screening) =>
    !place || (s.venue.geo !== null && distanceKm(place.point, s.venue.geo) <= params.radiusKm);
  const screenings = [...new Map(loaded.flat().map((s) => [s.id, s])).values()]
    .filter(within)
    .toSorted(byStart);
  const distances = place
    ? Object.fromEntries(
        screenings.map((s) => [
          s.venue.id,
          Math.round(distanceKm(place.point, s.venue.geo!) * 10) / 10,
        ]),
      )
    : {};
  return { ...base, films, state: "results", screenings, distances };
};
