import type { AppType } from "@pgtm/backend";
import { hc, type InferResponseType } from "hono/client";

/** Typed client for our API. Tests pass a fake `fetch`, so they never touch the network. */
export const createApi = (baseUrl: string, fetchImpl: typeof fetch = fetch) =>
  hc<AppType>(baseUrl, { fetch: fetchImpl });

export type Api = ReturnType<typeof createApi>;
export type Venue = InferResponseType<Api["v1"]["venues"]["$get"], 200>[number];
export type Screening = InferResponseType<Api["v1"]["screenings"]["$get"], 200>["items"][number];
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
