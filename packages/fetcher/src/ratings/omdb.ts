import type { Film, Rating } from "@pgtm/model";
import { z } from "zod";
import type { JsonCache } from "../lib/cache.ts";
import type { HttpClient } from "../lib/http.ts";

/**
 * OMDb (omdbapi.com): Rotten Tomatoes, Metacritic and IMDb scores by IMDb id, which TMDB
 * gives us, so the lookup is exact. Free key: 1,000 requests a day; data CC BY-NC 4.0
 * (non-commercial, attribution). Cached for a week, so a daily run asks only for new films.
 */
export const OMDB_URL = "https://www.omdbapi.com/";
const CACHE_MAX_AGE_MS = 7 * 24 * 3_600_000;

const OmdbResponse = z.looseObject({
  Response: z.string(),
  Error: z.string().optional(),
  Ratings: z.array(z.looseObject({ Source: z.string(), Value: z.string() })).optional(),
  imdbVotes: z.string().optional(),
});

const SOURCES: Record<string, Rating["source"]> = {
  "Rotten Tomatoes": "rotten-tomatoes",
  Metacritic: "metacritic",
  "Internet Movie Database": "imdb",
};

/** "93%" -> 93, "81/100" -> 81, "7.9/10" -> 79; undefined for "N/A" and the like. */
export const normalizeScore = (value: string): number | undefined => {
  const percent = value.match(/^(\d{1,3})%$/);
  if (percent) return Math.min(100, Number(percent[1]));
  const fraction = value.match(/^(\d+(?:\.\d+)?)\/(\d+)$/);
  if (fraction && Number(fraction[2]) > 0) {
    return Math.min(100, Math.round((Number(fraction[1]) / Number(fraction[2])) * 100));
  }
  return undefined;
};

/** Pure: an OMDb title response -> ratings. "Movie not found!" and the like -> []. */
export const parseOmdb = (raw: unknown): Rating[] => {
  const parsed = OmdbResponse.safeParse(raw);
  if (!parsed.success || parsed.data.Response !== "True") return [];
  const votes = Number((parsed.data.imdbVotes ?? "").replace(/,/g, ""));
  return (parsed.data.Ratings ?? []).flatMap((r) => {
    const source = SOURCES[r.Source];
    const score = normalizeScore(r.Value);
    if (!source || score === undefined) return [];
    return [
      {
        source,
        score,
        display: r.Value,
        ...(source === "imdb" && Number.isInteger(votes) && votes > 0 && { votes }),
      },
    ];
  });
};

/**
 * Asks OMDb for one title. The API key travels in the URL, and HTTP errors quote the URL,
 * so errors are rethrown without it: the key must never reach logs or the terminal.
 */
export const fetchOmdb = async (
  http: HttpClient,
  cache: JsonCache,
  apiKey: string,
  imdbId: string,
): Promise<Rating[]> => {
  // The cache key leaves out the API key on purpose.
  const raw = await cache.get(`omdb:${imdbId}`, CACHE_MAX_AGE_MS, async () => {
    try {
      return await http.getJson(OMDB_URL, { i: imdbId, apikey: apiKey });
    } catch (error) {
      const status = (error as { response?: { status?: number } }).response?.status;
      throw new Error(
        `OMDb request for ${imdbId} failed${status ? ` (HTTP ${status})` : ""}` +
          (status === 401 ? ": invalid key, or the daily limit (1,000) is used up" : ""),
      );
    }
  });
  return parseOmdb(raw);
};

/**
 * Adds OMDb ratings to films that have an IMDb id, keeping their TMDB rating. A failure
 * (network, limit) leaves the remaining films as they were and is reported once.
 */
export const addOmdbRatings = async (
  films: Film[],
  lookup: (imdbId: string) => Promise<Rating[]>,
): Promise<{ films: Film[]; rated: number; error?: string }> => {
  const out: Film[] = [];
  let rated = 0;
  let error: string | undefined;
  for (const film of films) {
    if (error || !film.imdbId) {
      out.push(film);
      continue;
    }
    try {
      const ratings = await lookup(film.imdbId);
      if (ratings.length) rated++;
      out.push({
        ...film,
        ratings: [...film.ratings.filter((r) => r.source === "tmdb"), ...ratings],
      });
    } catch (e) {
      error = (e as Error).message;
      out.push(film);
    }
  }
  return { films: out, rated, ...(error && { error }) };
};
