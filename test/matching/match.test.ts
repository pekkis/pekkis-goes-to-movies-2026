import { describe, expect, it } from "vitest";
import { matchListings } from "../../src/matching/match.ts";
import type { FilmListing } from "../../src/model/schema.ts";
import type { TmdbClient } from "../../src/tmdb/client.ts";
import type { MovieDetails, SearchResult } from "../../src/tmdb/raw.ts";
import { details } from "../tmdb/factory.ts";

const NOW = new Date("2026-10-09T12:00:00.000Z");

const fakeTmdb = (movies: MovieDetails[], searches: Record<string, number[]>) => {
  const calls: string[] = [];
  const byId = new Map(movies.map((m) => [m.id, m]));
  const client: TmdbClient = {
    search: async (query) => {
      calls.push(`search:${query}`);
      return (searches[query] ?? []).map((id): SearchResult => ({
        id,
        title: byId.get(id)!.title,
        original_title: byId.get(id)!.original_title,
        release_date: byId.get(id)!.release_date ?? null,
        popularity: 1,
      }));
    },
    movie: async (id) => {
      calls.push(`movie:${id}`);
      const movie = byId.get(id);
      if (!movie) throw new Error(`no movie ${id}`);
      return movie;
    },
  };
  return { client, calls };
};

const listing = (id: string, title: string, runtimeMinutes = 100): FilmListing => ({
  id: `biorex:film:${id}`,
  provider: "biorex",
  sourceId: id,
  title: { fi: title },
  runtimeMinutes,
  genres: [],
  countries: ["Yhdysvallat"],
});

describe("matchListings", () => {
  it("links a confident match and returns the film", async () => {
    const { client } = fakeTmdb([details({ id: 10, title: "Digger" })], { Digger: [10] });
    const result = await matchListings([listing("1", "Digger")], client, {}, NOW);

    expect(result.links.get("biorex:film:1")).toEqual({ filmId: "tmdb:10", method: "auto" });
    expect(result.films.map((f) => f.id)).toEqual(["tmdb:10"]);
    expect(result.unmatched).toEqual([]);
  });

  it("uses an alias without searching", async () => {
    const { client, calls } = fakeTmdb(
      [details({ id: 20, title: "PAW Patrol: The Dino Movie" })],
      {},
    );
    const result = await matchListings(
      [listing("1518", "Ryhmä Hau: Dinoelokuva")],
      client,
      { "biorex:film:1518": { tmdb: 20, title: "Ryhmä Hau: Dinoelokuva" } },
      NOW,
    );

    expect(result.links.get("biorex:film:1518")).toEqual({ filmId: "tmdb:20", method: "alias" });
    expect(calls).toEqual(["movie:20"]);
  });

  it("leaves a listing aliased to null alone", async () => {
    const { client, calls } = fakeTmdb([], {});
    const result = await matchListings(
      [listing("9", "Kotimainen lyhytelokuva")],
      client,
      { "biorex:film:9": { tmdb: null, title: "Kotimainen lyhytelokuva" } },
      NOW,
    );
    expect(result.links.size).toBe(0);
    expect(result.unmatched).toEqual([]);
    expect(calls).toEqual([]);
  });

  it("reports an unconfident listing with its candidates", async () => {
    const { client } = fakeTmdb([details({ id: 30, title: "The Odyssey", runtime: 86 })], {
      "The Odyssey": [30],
    });
    const result = await matchListings([listing("5", "The Odyssey", 172)], client, {}, NOW);

    expect(result.links.size).toBe(0);
    expect(result.unmatched).toEqual([
      {
        listingId: "biorex:film:5",
        title: "The Odyssey",
        reason: expect.stringContaining("runtime far"),
        candidates: [{ tmdbId: 30, title: "The Odyssey", year: 2026 }],
      },
    ]);
  });

  it("also searches the title prefix to find a renamed sequel", async () => {
    const { client, calls } = fakeTmdb(
      [details({ id: 40, title: "Practical Magic 2", runtime: 130 })],
      { "Practical Magic": [40] },
    );
    const result = await matchListings(
      [listing("7", "Practical Magic: Lumotut sisaret", 130)],
      client,
      {},
      NOW,
    );

    expect(calls).toContain("search:Practical Magic");
    expect(result.links.get("biorex:film:7")?.filmId).toBe("tmdb:40");
  });

  it("fetches a film shared by two listings only once into the catalog", async () => {
    const { client } = fakeTmdb([details({ id: 10, title: "Digger" })], { Digger: [10] });
    const result = await matchListings(
      [
        listing("1", "Digger"),
        { ...listing("1", "Digger"), id: "finnkino:film:99", provider: "finnkino" },
      ],
      client,
      {},
      NOW,
    );
    expect(result.films).toHaveLength(1);
    expect(result.links.size).toBe(2);
  });
});
