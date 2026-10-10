import { sql } from "kysely";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createDb } from "../src/db/database.ts";
import { ingestBatch, ingestFilms } from "../src/ingest/ingest.ts";
import { nextDay, parseLatLon, parseTime, resolveProviders } from "../src/search/filters.ts";
import { filmDetails, screeningsFor, searchFilms } from "../src/search/showtimes.ts";
import { batch, catalog, film, screening } from "./factory.ts";

const db = createDb(process.env["TEST_DATABASE_URL"]!);

beforeAll(async () => {
  await sql`truncate screenings, film_listings, auditoriums, venues, providers, films cascade`.execute(
    db,
  );
  await ingestFilms(
    db,
    catalog([
      film({ id: "tmdb:1", tmdbId: 1, title: { en: "The Odyssey" }, originalTitle: "The Odyssey" }),
      film({
        id: "tmdb:2",
        tmdbId: 2,
        title: { en: "PAW Patrol: The Dino Movie" },
        originalTitle: "PAW Patrol: The Dino Movie",
      }),
    ]),
  );
  const b = batch([
    screening("1", { listingId: "testchain:film:1", filmId: "tmdb:1" }),
    screening("2", {
      listingId: "testchain:film:1",
      filmId: "tmdb:1",
      businessDate: "2026-10-11",
      startsAt: "2026-10-11T18:00:00+03:00",
    }),
    screening("3", { listingId: "testchain:film:2", filmId: "tmdb:2" }),
    screening("4", { listingId: "testchain:film:3", filmId: undefined }),
  ]);
  const listing = b.listings[0]!;
  b.listings = [
    {
      ...listing,
      id: "testchain:film:1",
      sourceId: "1",
      title: { fi: "The Odyssey" },
      filmId: "tmdb:1",
    },
    {
      ...listing,
      id: "testchain:film:2",
      sourceId: "2",
      title: { fi: "Ryhmä Hau: Dinoelokuva" },
      filmId: "tmdb:2",
    },
    {
      ...listing,
      id: "testchain:film:3",
      sourceId: "3",
      title: { fi: "Ooppera: Così Fan Tutte" },
      filmId: undefined,
      match: undefined,
      kind: "event",
    },
  ];
  await ingestBatch(db, b);
});

afterAll(() => db.destroy());

describe("searchFilms", () => {
  it("tolerates typos", async () => {
    const [hit] = await searchFilms(db, "odysey");
    expect(hit).toMatchObject({ kind: "film", id: "tmdb:1" });
    expect(hit!.score).toBeGreaterThan(0.5);
  });

  it("finds a film by the title cinemas list it under", async () => {
    expect(await searchFilms(db, "ryhmä hau")).toEqual([{ kind: "film", id: "tmdb:2", score: 1 }]);
  });

  it("finds a listing that has no TMDB film", async () => {
    expect(await searchFilms(db, "cosi fan tutte")).toMatchObject([
      { kind: "listing", id: "testchain:film:3" },
    ]);
  });

  it("returns nothing below the threshold", async () => {
    expect(await searchFilms(db, "zzzz")).toEqual([]);
  });
});

describe("screeningsFor", () => {
  it("returns one business date of a film, in start order", async () => {
    const rows = await screeningsFor(db, { kind: "film", id: "tmdb:1", score: 1 }, "2026-10-10");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      city: "Jyväskylä",
      venue: "Testikino",
      screen: "Sali 1",
      audio: ["en"],
    });
  });

  it("returns screenings of an unmatched listing", async () => {
    const rows = await screeningsFor(
      db,
      { kind: "listing", id: "testchain:film:3", score: 1 },
      "2026-10-10",
    );
    expect(rows).toHaveLength(1);
  });

  const odyssey = { kind: "film", id: "tmdb:1", score: 1 } as const;

  it("filters by provider", async () => {
    expect(
      await screeningsFor(db, odyssey, "2026-10-10", { providerIds: ["testchain"] }),
    ).toHaveLength(1);
    expect(await screeningsFor(db, odyssey, "2026-10-10", { providerIds: ["other"] })).toEqual([]);
    expect(await screeningsFor(db, odyssey, "2026-10-10", { providerIds: [] })).toEqual([]);
  });

  it("filters by distance and reports it (Testikino is in central Jyväskylä)", async () => {
    // Kino Aurora, about 1 km away.
    const near = await screeningsFor(db, odyssey, "2026-10-10", {
      near: { lat: 62.2366, lon: 25.735, radiusKm: 5 },
    });
    expect(near).toHaveLength(1);
    expect(near[0]!.distanceKm).toBeGreaterThan(0.5);
    expect(near[0]!.distanceKm).toBeLessThan(1.5);

    // Helsinki is about 240 km away.
    const helsinki = { lat: 60.17, lon: 24.94 };
    expect(
      await screeningsFor(db, odyssey, "2026-10-10", { near: { ...helsinki, radiusKm: 50 } }),
    ).toEqual([]);
    expect(
      await screeningsFor(db, odyssey, "2026-10-10", { near: { ...helsinki, radiusKm: 300 } }),
    ).toHaveLength(1);
  });

  it("lists every film's screenings without a film, with titles", async () => {
    const all = await screeningsFor(db, undefined, "2026-10-10");
    expect(all.length).toBeGreaterThan(1);
    expect(new Set(all.map((r) => r.film)).size).toBeGreaterThan(1);
    const times = all.map((r) => r.startsAt.getTime());
    expect(times).toEqual(times.toSorted((a, b) => a - b));
  });

  it("filters by start time in Helsinki", async () => {
    // The fixture shows start at 18:00 Helsinki time.
    expect(await screeningsFor(db, odyssey, "2026-10-10", { after: "18:00" })).toHaveLength(1);
    expect(await screeningsFor(db, odyssey, "2026-10-10", { after: "18:01" })).toEqual([]);
  });

  it("filters by an upper start time, also past midnight", async () => {
    // The fixture show starts at 18:00.
    expect(await screeningsFor(db, odyssey, "2026-10-10", { before: "18:01" })).toHaveLength(1);
    expect(await screeningsFor(db, odyssey, "2026-10-10", { before: "18:00" })).toEqual([]);
    expect(
      await screeningsFor(db, odyssey, "2026-10-10", { after: "17:00", before: "19:00" }),
    ).toHaveLength(1);
    // before <= after: the window runs to the next morning.
    expect(
      await screeningsFor(db, odyssey, "2026-10-10", { after: "17:00", before: "02:00" }),
    ).toHaveLength(1);
    expect(
      await screeningsFor(db, odyssey, "2026-10-10", { after: "19:00", before: "02:00" }),
    ).toEqual([]);
  });

  it("filters by Rotten Tomatoes and IMDb scores (factory film: RT 93%, IMDb 7.9)", async () => {
    const rows = await screeningsFor(db, odyssey, "2026-10-10", {
      minScores: { rottenTomatoes: 90 },
    });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ rottenTomatoes: 93, imdb: 79 });
    expect(
      await screeningsFor(db, odyssey, "2026-10-10", { minScores: { rottenTomatoes: 94 } }),
    ).toEqual([]);
    expect(
      await screeningsFor(db, odyssey, "2026-10-10", { minScores: { imdb: 79 } }),
    ).toHaveLength(1);
    expect(await screeningsFor(db, odyssey, "2026-10-10", { minScores: { imdb: 80 } })).toEqual([]);
    // A listing without a TMDB film has no scores, so any minimum leaves it out.
    const unmatched = { kind: "listing", id: "testchain:film:3", score: 1 } as const;
    expect(await screeningsFor(db, unmatched, "2026-10-10", { minScores: { imdb: 1 } })).toEqual(
      [],
    );
  });

  it("has no distance without a point", async () => {
    expect((await screeningsFor(db, odyssey, "2026-10-10"))[0]!.distanceKm).toBeNull();
  });

  it("skips removed screenings", async () => {
    await db
      .updateTable("screenings")
      .set({ removedAt: new Date() })
      .where("sourceId", "=", "3")
      .execute();
    expect(await screeningsFor(db, { kind: "film", id: "tmdb:2", score: 1 }, "2026-10-10")).toEqual(
      [],
    );
  });
});

it("filmDetails carries ratings in a fixed source order", async () => {
  expect((await filmDetails(db, "tmdb:1"))?.ratings).toEqual([
    { source: "rotten-tomatoes", score: 93, display: "93%", votes: null },
    { source: "imdb", score: 79, display: "7.9/10", votes: 120000 },
  ]);
});

it("filmDetails falls back to the cinemas' Finnish title", async () => {
  expect(await filmDetails(db, "tmdb:2")).toMatchObject({
    titleFi: null,
    localTitle: "Ryhmä Hau: Dinoelokuva",
  });
});

describe("filters", () => {
  it("parses a point, also in a map link's @lat,lon form", () => {
    expect(parseLatLon("62.24,25.75")).toEqual({ lat: 62.24, lon: 25.75 });
    expect(parseLatLon(" 60.7381466, 24.7742851 ")).toEqual({ lat: 60.7381466, lon: 24.7742851 });
    expect(parseLatLon("@60.7381466,24.7742851,17z")).toEqual({ lat: 60.7381466, lon: 24.7742851 });
    expect(parseLatLon("Jyväskylä")).toBeUndefined();
    expect(parseLatLon("95,25")).toBeUndefined();
  });

  it("steps to the next day across months and years", () => {
    expect(nextDay("2026-10-10")).toBe("2026-10-11");
    expect(nextDay("2026-10-31")).toBe("2026-11-01");
    expect(nextDay("2026-12-31")).toBe("2027-01-01");
  });

  it("parses a time of day", () => {
    expect(parseTime("18:00")).toBe("18:00");
    expect(parseTime("9.30")).toBe("09:30");
    expect(parseTime("24:00")).toBeUndefined();
    expect(parseTime("tonight")).toBeUndefined();
  });

  it("resolves provider ids and platforms, and reports unknown names", async () => {
    expect(await resolveProviders(db, ["testchain"])).toMatchObject({
      ids: ["testchain"],
      unknown: [],
    });
    expect(await resolveProviders(db, ["CUSTOM"])).toMatchObject({
      ids: ["testchain"],
      unknown: [],
    });
    const bad = await resolveProviders(db, ["nope"]);
    expect(bad.unknown).toEqual(["nope"]);
    expect(bad.known).toContain("testchain");
  });
});
