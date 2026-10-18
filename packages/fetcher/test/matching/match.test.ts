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
      if (!movie) {
        throw new Error(`no movie ${id}`);
      }
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
  it("reads a year written into the title, so a same-named film of another year is not chosen", async () => {
    // Pajakkakino, 2026-10-16: "NOSFERATU (1922)", 95 min, matched a 2023 "Nosferatu" (92 min).
    const { client } = fakeTmdb(
      [
        details({ id: 653, title: "Nosferatu", release_date: "1922-02-16", runtime: 94 }),
        details({ id: 394151, title: "Nosferatu", release_date: "2023-11-17", runtime: 92 }),
      ],
      { NOSFERATU: [394151, 653] },
    );
    // No countries, as Pajakkakino states none: the title's year is the only thing to go on.
    const nosferatu = { ...listing("1", "NOSFERATU (1922)", 95), countries: [] };
    const result = await matchListings([nosferatu], client, {}, NOW);
    expect(result.links.get("biorex:film:1")?.filmId).not.toBe("tmdb:394151");
  });

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

  it("keeps a sibling's link when the anchor has left the programme (2026-10-18)", async () => {
    const { client } = fakeTmdb(
      [details({ id: 20, title: "Practical Magic 2", runtime: 130 })],
      {},
    );
    const finnkino: FilmListing = {
      ...listing("HO1", "Practical Magic: Lumotut sisaret", 127),
      id: "finnkino:film:HO1",
      provider: "finnkino",
      countries: [],
    };
    const anchor = listing("1", "Practical Magic: Lumotut sisaret", 127);
    const aliases = { "biorex:film:1": { tmdb: 20, title: "x" } };
    const day1 = await matchListings([anchor, finnkino], client, aliases, NOW);
    expect(day1.links.get("finnkino:film:HO1")?.method).toBe("sibling");

    // The next day BioRex no longer shows it: Finnkino's listing keeps its film.
    const day2 = await matchListings([finnkino], client, {}, NOW, day1.memory);
    expect(day2.links.get("finnkino:film:HO1")).toEqual({
      filmId: "tmdb:20",
      method: "remembered",
    });
    expect(day2.unmatched).toEqual([]);
    expect(day2.films.map((f) => f.tmdbId)).toEqual([20]);
  });

  it("forgets a remembered link when the listing's title or runtime changed", async () => {
    const { client } = fakeTmdb([details({ id: 20, title: "X", runtime: 100 })], {});
    const memory = {
      "biorex:film:1": {
        filmId: "tmdb:20",
        titleKey: "digger",
        runtimeMinutes: 100,
        lastSeen: NOW.toISOString(),
      },
    };
    const renamed = await matchListings([listing("1", "Other Film")], client, {}, NOW, memory);
    expect(renamed.links.has("biorex:film:1")).toBe(false);
    const longer = await matchListings([listing("1", "Digger", 130)], client, {}, NOW, memory);
    expect(longer.links.has("biorex:film:1")).toBe(false);
    const same = await matchListings([listing("1", "Digger", 101)], client, {}, NOW, memory);
    expect(same.links.get("biorex:film:1")?.method).toBe("remembered");
  });

  it("lets a fresh confident match win over a memory", async () => {
    const { client } = fakeTmdb(
      [details({ id: 21, title: "Digger", runtime: 100 }), details({ id: 20, title: "Y" })],
      { Digger: [21] },
    );
    const memory = {
      "biorex:film:1": {
        filmId: "tmdb:20",
        titleKey: "digger",
        runtimeMinutes: 100,
        lastSeen: NOW.toISOString(),
      },
    };
    const result = await matchListings([listing("1", "Digger")], client, {}, NOW, memory);
    expect(result.links.get("biorex:film:1")).toEqual({ filmId: "tmdb:21", method: "auto" });
    expect(result.memory["biorex:film:1"]?.filmId).toBe("tmdb:21");
  });

  it("scores a classic of the listing's year even behind five recent namesakes (Ghost, 1990)", async () => {
    const recent = [1, 2, 3, 4, 5].map((n) =>
      details({ id: n, title: `Ghost ${n}`, release_date: "2025-01-01", runtime: 90 }),
    );
    const ghost = details({ id: 251, title: "Ghost", release_date: "1990-07-13", runtime: 127 });
    const { client } = fakeTmdb([...recent, ghost], { Ghost: [1, 2, 3, 4, 5, 251] });
    const result = await matchListings(
      [{ ...listing("1", "Ghost", 126), year: 1990 }],
      client,
      {},
      NOW,
    );
    expect(result.links.get("biorex:film:1")).toEqual({ filmId: "tmdb:251", method: "auto" });
  });

  it("does not auto-match an event that states no runtime", async () => {
    // Julia's "Don Giovanni (Vicenza festivaali / Mozart)" matched a 2023 Don Giovanni.
    const { client, calls } = fakeTmdb([details({ id: 30, title: "Don Giovanni" })], {
      "Don Giovanni": [30],
    });
    const { runtimeMinutes: _none, ...noRuntime } = listing("10", "Don Giovanni");
    const result = await matchListings([{ ...noRuntime, kind: "event" }], client, {}, NOW);
    expect(result.links.size).toBe(0);
    expect(result.unmatched).toEqual([]);
    expect(calls).toEqual([]);
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
