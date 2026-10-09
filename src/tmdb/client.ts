import { noCache, type JsonCache } from "../lib/cache.ts";
import { createHttpClient, type HttpClient } from "../lib/http.ts";
import { MovieDetails, SearchResponse, type SearchResult } from "./raw.ts";

const API = "https://api.themoviedb.org/3";
const DAY = 24 * 60 * 60 * 1000;

export type TmdbClient = {
  search: (query: string) => Promise<SearchResult[]>;
  movie: (id: number) => Promise<MovieDetails>;
};

/** TMDB allows ~40 req/s; we stay well below. */
export const createTmdbHttp = (token: string, contact?: string): HttpClient =>
  createHttpClient({
    headers: { authorization: `Bearer ${token}` },
    ...(contact && { contact }),
    concurrency: 4,
    intervalCap: 20,
    intervalMs: 1000,
  });

export const createTmdbClient = (http: HttpClient, cache: JsonCache = noCache): TmdbClient => ({
  search: async (query) => {
    const params = { query, language: "fi-FI", include_adult: "false" };
    const raw = await cache.get(`search:${JSON.stringify(params)}`, DAY, () =>
      http.getJson(`${API}/search/movie`, params),
    );
    return SearchResponse.parse(raw).results;
  },
  movie: async (id) => {
    const params = {
      language: "fi-FI",
      append_to_response: "translations,alternative_titles,release_dates,videos,images",
      include_image_language: "fi,en,null",
      include_video_language: "fi,en,null",
    };
    const raw = await cache.get(`movie:${id}:${JSON.stringify(params)}`, 7 * DAY, () =>
      http.getJson(`${API}/movie/${id}`, params),
    );
    return MovieDetails.parse(raw);
  },
});
