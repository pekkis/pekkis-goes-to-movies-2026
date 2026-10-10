import { sql } from "kysely";
import { afterAll, beforeEach, describe, expect, it } from "vitest";
import { createDb } from "../src/db/database.ts";
import { ingestBatch, ingestFilms } from "../src/ingest/ingest.ts";
import { batch, catalog, film, screening } from "./factory.ts";

const db = createDb(process.env["TEST_DATABASE_URL"]!);

beforeEach(async () => {
  await sql`truncate screenings, film_listings, auditoriums, venues, providers, films cascade`.execute(
    db,
  );
  await ingestFilms(db, catalog());
});

afterAll(() => db.destroy());

const later = (iso: string, hours: number) =>
  new Date(Date.parse(iso) + hours * 3_600_000).toISOString();

describe("ingestBatch", () => {
  it("inserts everything and round-trips through CamelCasePlugin", async () => {
    const result = await ingestBatch(db, batch([screening("1"), screening("2")]));
    expect(result).toEqual({ inserted: 2, updated: 0, removed: 0 });

    const row = await db
      .selectFrom("screenings")
      .selectAll()
      .where("id", "=", "testchain:show:1")
      .executeTakeFirstOrThrow();
    expect(row).toMatchObject({
      venueId: "testchain:venue:1",
      filmId: "tmdb:100",
      businessDate: "2026-10-10",
      subtitlesLanguages: ["fi", "sv"],
      formats: ["imax"],
      removedAt: null,
    });
    expect(row.startsAt.toISOString()).toBe("2026-10-10T15:00:00.000Z");
    expect(row.firstSeenAt.toISOString()).toBe("2026-10-09T12:00:00.000Z");
  });

  it("is idempotent and bumps last_seen_at on the next fetch", async () => {
    await ingestBatch(db, batch([screening("1")]));
    const next = later(batch([]).fetchedAt, 6);
    const result = await ingestBatch(
      db,
      batch([screening("1", { availability: "sold-out" })], { fetchedAt: next }),
    );
    expect(result).toEqual({ inserted: 0, updated: 1, removed: 0 });

    const row = await db.selectFrom("screenings").selectAll().executeTakeFirstOrThrow();
    expect(row.availability).toBe("sold-out");
    expect(row.firstSeenAt.toISOString()).toBe("2026-10-09T12:00:00.000Z");
    expect(row.lastSeenAt.toISOString()).toBe(next);
  });

  it("marks a future screening missing from the window as removed, and restores it if it returns", async () => {
    await ingestBatch(db, batch([screening("1"), screening("2")]));
    const next = later(batch([]).fetchedAt, 6);

    expect(await ingestBatch(db, batch([screening("1")], { fetchedAt: next }))).toMatchObject({
      removed: 1,
    });
    const gone = await db
      .selectFrom("screenings")
      .select("removedAt")
      .where("sourceId", "=", "2")
      .executeTakeFirstOrThrow();
    expect(gone.removedAt?.toISOString()).toBe(next);

    await ingestBatch(db, batch([screening("1"), screening("2")], { fetchedAt: later(next, 6) }));
    const back = await db
      .selectFrom("screenings")
      .select("removedAt")
      .where("sourceId", "=", "2")
      .executeTakeFirstOrThrow();
    expect(back.removedAt).toBeNull();
  });

  it("never removes past screenings or days outside the fetched window", async () => {
    const past = screening("past", {
      startsAt: "2026-10-09T10:00:00+03:00",
      businessDate: "2026-10-09",
    });
    const outside = screening("outside", {
      startsAt: "2026-10-20T18:00:00+03:00",
      businessDate: "2026-10-20",
    });
    await ingestBatch(
      db,
      batch([past, outside], { window: { from: "2026-10-09", to: "2026-10-20" } }),
    );

    const result = await ingestBatch(db, batch([], { fetchedAt: later(batch([]).fetchedAt, 1) }));
    expect(result.removed).toBe(0);
    const removed = await db
      .selectFrom("screenings")
      .select("id")
      .where("removedAt", "is not", null)
      .execute();
    expect(removed).toEqual([]);
  });

  it("leaves venues the batch does not list alone (a partial --venue pull)", async () => {
    await ingestBatch(db, batch([screening("1")]));
    const partial = batch([], { fetchedAt: later(batch([]).fetchedAt, 1) });
    partial.venues = [];
    partial.auditoriums = [];
    expect((await ingestBatch(db, partial)).removed).toBe(0);
  });

  it("keeps listings without a film", async () => {
    const b = batch([screening("1", { filmId: undefined })]);
    b.listings = [{ ...b.listings[0]!, filmId: undefined, match: undefined }];
    await ingestBatch(db, b);
    const listing = await db.selectFrom("filmListings").selectAll().executeTakeFirstOrThrow();
    expect(listing).toMatchObject({ filmId: null, match: null, kind: "film" });
  });
});

describe("ingestFilms", () => {
  it("updates an existing film", async () => {
    await ingestFilms(db, catalog([film({ title: { fi: "Uusi nimi" } })]));
    const row = await db.selectFrom("films").selectAll().executeTakeFirstOrThrow();
    expect(row).toMatchObject({
      titleFi: "Uusi nimi",
      titleEn: null,
      trailers: [{ site: "YouTube", key: "abc", name: "Trailer" }],
    });
  });
});
