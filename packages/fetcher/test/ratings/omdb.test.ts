import type { Film } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import { noCache } from "../../src/lib/cache.ts";
import type { HttpClient } from "../../src/lib/http.ts";
import { addOmdbRatings, fetchOmdb, normalizeScore, parseOmdb } from "../../src/ratings/omdb.ts";
import { tmdbRating } from "../../src/tmdb/film.ts";
import type { MovieDetails } from "../../src/tmdb/raw.ts";
import { loadFixture } from "../fixtures.ts";

describe("normalizeScore", () => {
  it.each([
    ["87%", 87],
    ["86/100", 86],
    ["8.0/10", 80],
    ["7.86/10", 79],
    ["100%", 100],
  ])("%s -> %d", (value, score) => {
    expect(normalizeScore(value)).toBe(score);
  });

  it("rejects what is not a score", () => {
    expect(normalizeScore("N/A")).toBeUndefined();
    expect(normalizeScore("8/0")).toBeUndefined();
  });
});

describe("parseOmdb", () => {
  it("reads Rotten Tomatoes, Metacritic and IMDb (with votes) from a real response", () => {
    expect(parseOmdb(loadFixture("omdb", "nausicaa.json"))).toEqual([
      { source: "imdb", score: 80, display: "8.0/10", votes: 199714 },
      { source: "rotten-tomatoes", score: 87, display: "87%" },
      { source: "metacritic", score: 86, display: "86/100" },
    ]);
  });

  it("returns nothing for misses and unknown sources", () => {
    expect(parseOmdb({ Response: "False", Error: "Incorrect IMDb ID." })).toEqual([]);
    expect(
      parseOmdb({ Response: "True", Ratings: [{ Source: "Letterboxd", Value: "4.1/5" }] }),
    ).toEqual([]);
    expect(parseOmdb("nope")).toEqual([]);
  });
});

describe("fetchOmdb", () => {
  it("never puts the API key into an error", async () => {
    const failing: HttpClient = {
      getJson: async (url, params) => {
        throw Object.assign(new Error(`Request failed: GET ${url}?apikey=${params?.["apikey"]}`), {
          response: { status: 401 },
        });
      },
    };
    const error = await fetchOmdb(failing, noCache, "SECRETKEY", "tt0087544").catch(
      (e: Error) => e,
    );
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).not.toContain("SECRETKEY");
    expect((error as Error).message).toMatch(/HTTP 401.*daily limit/);
  });
});

describe("addOmdbRatings", () => {
  const film = (id: number, imdbId?: string): Film =>
    ({
      id: `tmdb:${id}`,
      tmdbId: id,
      ...(imdbId && { imdbId }),
      ratings: [{ source: "tmdb", score: 79, display: "7.9/10", votes: 4234 }],
    }) as Film;

  it("adds ratings, keeps TMDB's, and skips films without an IMDb id", async () => {
    const result = await addOmdbRatings([film(1, "tt1"), film(2)], async () => [
      { source: "rotten-tomatoes", score: 87, display: "87%" },
    ]);
    expect(result.rated).toBe(1);
    expect(result.films[0]!.ratings.map((r) => r.source)).toEqual(["tmdb", "rotten-tomatoes"]);
    expect(result.films[1]!.ratings.map((r) => r.source)).toEqual(["tmdb"]);
  });

  it("stops at the first failure and keeps the remaining films as they were", async () => {
    let calls = 0;
    const result = await addOmdbRatings([film(1, "tt1"), film(2, "tt2")], async () => {
      calls++;
      throw new Error("OMDb request for tt1 failed (HTTP 401)");
    });
    expect(calls).toBe(1);
    expect(result.error).toMatch(/HTTP 401/);
    expect(result.films).toHaveLength(2);
  });
});

describe("tmdbRating", () => {
  const details = (vote_average: number | null, vote_count: number | null) =>
    ({ vote_average, vote_count }) as MovieDetails;

  it("uses TMDB's score once enough people voted", () => {
    expect(tmdbRating(details(7.94, 4234))).toEqual([
      { source: "tmdb", score: 79, display: "7.9/10", votes: 4234 },
    ]);
    expect(tmdbRating(details(9.5, 3))).toEqual([]);
    expect(tmdbRating(details(null, null))).toEqual([]);
  });
});
