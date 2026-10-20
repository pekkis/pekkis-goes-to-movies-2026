import type { AppType } from "@pgtm/backend";
import { hc, type InferResponseType } from "hono/client";

/** Typed client for our API. Tests pass a fake `fetch`, so they never touch the network. */
export const createApi = (baseUrl: string, fetchImpl: typeof fetch = fetch) =>
  hc<AppType>(baseUrl, { fetch: fetchImpl });

export type Api = ReturnType<typeof createApi>;
export type Venue = InferResponseType<Api["v1"]["venues"]["$get"], 200>[number];
export type Screening = InferResponseType<Api["v1"]["screenings"]["$get"], 200>["items"][number];
export type Film = InferResponseType<Api["v1"]["films"][":id"]["$get"], 200>;
export type FilmOpening = InferResponseType<Api["v1"]["films"]["openings"]["$get"], 200>[number];
export type FilmPlaying = InferResponseType<Api["v1"]["films"]["playing"]["$get"], 200>[number];
export type FilmSummary = InferResponseType<
  Api["v1"]["films"]["search"]["$get"],
  200
>[number]["film"];

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, path: string) {
    super(`API ${path} answered ${status}`);
    this.status = status;
  }
}

export const listVenues = async (api: Api, city?: string): Promise<Venue[]> => {
  const res = await api.v1.venues.$get({ query: city ? { city } : {} });
  if (!res.ok) {
    throw new ApiError(res.status, "/v1/venues");
  }
  return res.json();
};

/**
 * One day's screenings for a city, a venue or a map box (`minLon,minLat,maxLon,maxLat`),
 * following `nextCursor` through every page.
 */
export const dayScreenings = async (
  api: Api,
  query: { city: string } | { venue: string } | { bbox: string },
  date?: string,
): Promise<{ date: string; items: Screening[] }> => {
  const items: Screening[] = [];
  let cursor: string | undefined;
  let shown = date ?? "";
  do {
    const res = await api.v1.screenings.$get({
      query: { ...query, ...(date && { date }), ...(cursor && { cursor }) },
    });
    if (!res.ok) {
      throw new ApiError(res.status, "/v1/screenings");
    }
    const page = await res.json();
    items.push(...page.items);
    shown = page.date;
    cursor = page.nextCursor ?? undefined;
  } while (cursor);
  return { date: shown, items };
};

/** Films showing anywhere whose titles resemble `q` (fuzzy, any language), best first. */
export const searchFilms = async (api: Api, q: string, limit = 3): Promise<FilmSummary[]> => {
  const res = await api.v1.films.search.$get({ query: { q, limit: String(limit) } });
  if (!res.ok) {
    throw new ApiError(res.status, "/v1/films/search");
  }
  return (await res.json()).map((hit) => hit.film);
};

/** Where and when one film plays on one day, optionally inside a map box. */
export const filmDayScreenings = async (
  api: Api,
  filmId: string,
  date: string,
  bbox?: string,
): Promise<Screening[]> => {
  const res = await api.v1.films[":id"].screenings.$get({
    param: { id: filmId },
    query: { date, ...(bbox && { bbox }) },
  });
  if (res.status === 404) {
    return [];
  }
  if (!res.ok) {
    throw new ApiError(res.status, `/v1/films/${filmId}/screenings`);
  }
  return (await res.json()).items;
};

/** A film (TMDB) or listing with everything we know; undefined for an unknown id. */
export const getFilm = async (api: Api, id: string): Promise<Film | undefined> => {
  const res = await api.v1.films[":id"].$get({ param: { id } });
  if (res.status === 404) {
    return undefined;
  }
  // The typed response knows only 200 and 404; a server error is still possible.
  const any = res as Response;
  if (!any.ok) {
    throw new ApiError(any.status, `/v1/films/${id}`);
  }
  return res.json();
};

/**
 * Films whose first showing falls between two programme days, earliest first; with
 * `playing`, only those with a screening between those days too.
 */
export const filmOpenings = async (
  api: Api,
  from: string,
  to: string,
  playing?: { from: string; to: string },
  /** Leave out films with a screening carrying this tag (within `playing`). */
  excludeTag?: string,
): Promise<FilmOpening[]> => {
  const res = await api.v1.films.openings.$get({
    query: {
      from,
      to,
      ...(playing && { playingFrom: playing.from, playingTo: playing.to }),
      ...(excludeTag && { excludeTag }),
    },
  });
  if (!res.ok) {
    throw new ApiError(res.status, "/v1/films/openings");
  }
  return res.json();
};

/** Films with screenings between two days (only those with `tag`, when given), with the first. */
export const filmsPlaying = async (
  api: Api,
  from: string,
  to: string,
  tag?: string,
): Promise<FilmPlaying[]> => {
  const res = await api.v1.films.playing.$get({ query: { from, to, ...(tag && { tag }) } });
  if (!res.ok) {
    throw new ApiError(res.status, "/v1/films/playing");
  }
  return res.json();
};
