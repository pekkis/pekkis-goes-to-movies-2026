import { describe, expect, it } from "vitest";
import { matchListings } from "../../src/matching/match.ts";
import type { FilmListing } from "@pgtm/model";
import type { TmdbClient } from "../../src/tmdb/client.ts";
import type { MovieDetails, SearchResult } from "../../src/tmdb/raw.ts";
import { details } from "../tmdb/factory.ts";

const NOW = new Date("2026-10-09T12:00:00.000Z");

const fakeTmdb = (
  movies: MovieDetails[],
  searches: Record<string, number[]>,
  imdb: Record<string, number> = {},
) => {
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
    findByImdb: async (imdbId) => {
      calls.push(`find:${imdbId}`);
      return imdb[imdbId];
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
  kind: "film",
});

describe("matchListings", () => {
  it("links a confident match and returns the film", async () => {
    const { client } = fakeTmdb([details({ id: 10, title: "Digger" })], { Digger: [10] });
    const result = await matchListings([listing("1", "Digger")], client, {}, NOW);

    expect(result.links.get("biorex:film:1")).toEqual({ filmId: "tmdb:10", method: "auto" });
    expect(result.films.map((f) => f.id)).toEqual(["tmdb:10"]);
    expect(result.unmatched).toEqual([]);
  });

  it("links by the provider's IMDb id without searching", async () => {
    const { client, calls } = fakeTmdb(
      [details({ id: 30, title: "Casper", release_date: "1995-05-26" })],
      {},
      {
        tt0112642: 30,
      },
    );
    const result = await matchListings(
      [{ ...listing("1", "Casper"), imdbId: "tt0112642" }],
      client,
      {},
      NOW,
    );
    expect(result.links.get("biorex:film:1")).toEqual({ filmId: "tmdb:30", method: "imdb" });
    expect(calls).toEqual(["find:tt0112642", "movie:30"]);
  });

  it("falls back to searching when TMDB does not know the IMDb id", async () => {
    const { client } = fakeTmdb([details({ id: 10, title: "Digger" })], { Digger: [10] });
    const result = await matchListings(
      [{ ...listing("1", "Digger"), imdbId: "tt999" }],
      client,
      {},
      NOW,
    );
    expect(result.links.get("biorex:film:1")).toEqual({ filmId: "tmdb:10", method: "auto" });
  });

  it("matches an old film by its original title and year", async () => {
    // Finnish title unknown to TMDB; the original title and the listing's year are certain.
    const { client, calls } = fakeTmdb(
      [details({ id: 40, title: "That Darn Cat!", release_date: "1965-12-02", runtime: 116 })],
      { "That Darn Cat!": [40] },
    );
    const result = await matchListings(
      [{ ...listing("2", "Pahuksen katti", 116), originalTitle: "That Darn Cat!", year: 1965 }],
      client,
      {},
      NOW,
    );
    expect(calls).toContain("search:That Darn Cat!");
    expect(result.links.get("biorex:film:2")).toEqual({ filmId: "tmdb:40", method: "auto" });
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

  it("searches without a trailing qualifier", async () => {
    const { client, calls } = fakeTmdb([details({ id: 50, title: "Vaiana", runtime: 115 })], {
      Vaiana: [50],
    });
    const result = await matchListings([listing("8", "Vaiana (liveaction)", 115)], client, {}, NOW);
    expect(calls).toContain("search:Vaiana");
    expect(result.links.get("biorex:film:8")?.filmId).toBe("tmdb:50");
  });

  it("links a listing to the film another provider matched with the same title and runtime", async () => {
    const { client } = fakeTmdb(
      [details({ id: 20, title: "PAW Patrol: The Dino Movie", runtime: 88 })],
      {},
    );
    const finnkino: FilmListing = {
      ...listing("HO1", "Ryhmä Hau: Dinoelokuva", 87),
      id: "finnkino:film:HO1",
      provider: "finnkino",
      countries: [],
    };
    const result = await matchListings(
      [listing("1518", "Ryhmä Hau: Dinoelokuva", 88), finnkino],
      client,
      { "biorex:film:1518": { tmdb: 20, title: "Ryhmä Hau: Dinoelokuva" } },
      NOW,
    );
    expect(result.links.get("finnkino:film:HO1")).toEqual({ filmId: "tmdb:20", method: "sibling" });
    expect(result.unmatched).toEqual([]);
  });

  it("does not treat a same-titled listing with a different runtime as a sibling", async () => {
    const { client } = fakeTmdb([details({ id: 20, title: "X", runtime: 88 })], {});
    const result = await matchListings(
      [
        listing("1", "Remake", 88),
        { ...listing("HO1", "Remake", 120), id: "finnkino:film:HO1", provider: "finnkino" },
      ],
      client,
      { "biorex:film:1": { tmdb: 20, title: "Remake" } },
      NOW,
    );
    expect(result.links.has("finnkino:film:HO1")).toBe(false);
    expect(result.unmatched.map((u) => u.listingId)).toEqual(["finnkino:film:HO1"]);
  });

  it("does not report an unmatched event", async () => {
    const { client } = fakeTmdb([], {});
    const result = await matchListings(
      [{ ...listing("9", "Ooppera: Così Fan Tutte", 237), kind: "event" }],
      client,
      {},
      NOW,
    );
    expect(result.unmatched).toEqual([]);
  });
});
