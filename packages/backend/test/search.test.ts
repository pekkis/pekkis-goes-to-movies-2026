import { sql } from "kysely";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createDb } from "../src/db/database.ts";
import { ingestBatch, ingestFilms } from "../src/ingest/ingest.ts";
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

it("filmDetails falls back to the cinemas' Finnish title", async () => {
  expect(await filmDetails(db, "tmdb:2")).toMatchObject({
    titleFi: null,
    localTitle: "Ryhmä Hau: Dinoelokuva",
  });
});
