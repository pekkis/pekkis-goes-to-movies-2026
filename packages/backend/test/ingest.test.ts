import { sql } from "kysely";
import { afterAll, beforeEach, describe, expect, it } from "vitest";
import { createDb } from "../src/db/database.ts";
import { ingestBatch, ingestFilms, ingestPullStatus, looksPartial } from "../src/ingest/ingest.ts";
import { FETCHED_AT, batch, catalog, film, screening } from "./factory.ts";

const db = createDb(process.env["TEST_DATABASE_URL"]!);

beforeEach(async () => {
  await sql`truncate screenings, film_listings, auditoriums, venues, providers, films, series cascade`.execute(
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
    expect(result).toEqual({ inserted: 2, updated: 0, removed: 0, removalsSkipped: false });

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

  it("stores raw labels and the batch's series catalogue, updating renamed series", async () => {
    const labels = [{ source: "etiketti.tag", text: "Kiirehdi" }];
    const kuvi = { id: "kuvi-aluesarja", name: "Kuvin aluesarja", kind: "strand" as const };
    await ingestBatch(
      db,
      batch([screening("1", { labels, series: [kuvi.id] })], { series: [kuvi] }),
    );
    await ingestBatch(
      db,
      batch([screening("1", { labels, series: [kuvi.id] })], {
        series: [{ ...kuvi, name: "KUVIn aluesarja", kind: "distributor-series" }],
      }),
    );
    const row = await db
      .selectFrom("screenings")
      .select(["labels", "series"])
      .where("id", "=", "testchain:show:1")
      .executeTakeFirstOrThrow();
    expect(row).toEqual({ labels, series: ["kuvi-aluesarja"] });
    expect(await db.selectFrom("series").select(["id", "name", "kind"]).execute()).toEqual([
      { id: "kuvi-aluesarja", name: "KUVIn aluesarja", kind: "distributor-series" },
    ]);
  });

  it("is idempotent and bumps last_seen_at on the next fetch", async () => {
    await ingestBatch(db, batch([screening("1")]));
    const next = later(batch([]).fetchedAt, 6);
    const result = await ingestBatch(
      db,
      batch([screening("1", { availability: "sold-out" })], { fetchedAt: next }),
    );
    expect(result).toEqual({ inserted: 0, updated: 1, removed: 0, removalsSkipped: false });

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

  it("leaves a show about to start alone: sources drop it once sales close (2026-10-22)", async () => {
    // Fetched at 15:00 Helsinki time: 15:10 is about to start, 21:00 is later in the day.
    const soon = screening("soon", { startsAt: "2026-10-09T15:10:00+03:00" });
    const evening = screening("evening", { startsAt: "2026-10-09T21:00:00+03:00" });
    const other = screening("other", { startsAt: "2026-10-09T19:00:00+03:00" });
    await ingestBatch(db, batch([soon, evening, other]));

    const result = await ingestBatch(db, batch([other]));
    expect(result.removed).toBe(1);
    const removed = await db
      .selectFrom("screenings")
      .select("sourceId")
      .where("removedAt", "is not", null)
      .execute();
    expect(removed.map((r) => r.sourceId)).toEqual(["evening"]);
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

  it("infers no removals from an incomplete batch (part of the source failed to parse)", async () => {
    await ingestBatch(db, batch([screening("1"), screening("2")]));
    const broken = batch([screening("1")], { fetchedAt: later(batch([]).fetchedAt, 6) });
    broken.warnings = [{ code: "invalid-response", message: "location 2 did not parse" }];
    expect(await ingestBatch(db, broken)).toMatchObject({
      removed: 0,
      removalsSkipped: "incomplete",
    });
    const second = await db
      .selectFrom("screenings")
      .select("removedAt")
      .where("sourceId", "=", "2")
      .executeTakeFirstOrThrow();
    expect(second.removedAt).toBeNull();

    // Deliberate skips do not make a batch incomplete.
    const skipped = batch([screening("1")], { fetchedAt: later(batch([]).fetchedAt, 7) });
    skipped.warnings = [{ code: "unclaimed-room", message: "room 24 belongs to no venue" }];
    expect(await ingestBatch(db, skipped)).toMatchObject({ removed: 1, removalsSkipped: false });
  });

  it("infers no removals from an empty batch with no warnings (a parser gone silent)", async () => {
    await ingestBatch(db, batch([screening("1"), screening("2")]));
    const empty = batch([], { fetchedAt: later(batch([]).fetchedAt, 1) });
    expect(await ingestBatch(db, empty)).toMatchObject({ removed: 0, removalsSkipped: "empty" });
    const removed = await db
      .selectFrom("screenings")
      .select("id")
      .where("removedAt", "is not", null)
      .execute();
    expect(removed).toEqual([]);

    // One screening left is a programme, not a silence: the other is removed.
    const one = batch([screening("1")], { fetchedAt: later(batch([]).fetchedAt, 2) });
    expect(await ingestBatch(db, one)).toMatchObject({ removed: 1, removalsSkipped: false });
  });

  it("infers no removals when most upcoming screenings vanish at once (a source answering in part)", async () => {
    // Twelve future shows held; the next fetch brings only one (Cine Mäntsälä, 2026-10-20).
    const shows = Array.from({ length: 12 }, (_, i) =>
      screening(`p${i}`, { startsAt: later("2026-10-10T18:00:00+03:00", i) }),
    );
    await ingestBatch(db, batch(shows));
    const partial = await ingestBatch(db, batch([shows[0]!], { fetchedAt: later(FETCHED_AT, 1) }));
    expect(partial).toMatchObject({ removed: 0, removalsSkipped: "drop" });
    const removed = await db
      .selectFrom("screenings")
      .select("id")
      .where("removedAt", "is not", null)
      .execute();
    expect(removed).toEqual([]);
  });

  it.each([
    [12, 1, true],
    [12, 6, false],
    // Under half but only 7 fewer: a small cinema's quiet week, not a broken source.
    [12, 5, false],
    [30, 14, true],
    [8, 0, false],
    [8, 1, false],
  ])("looksPartial(held %i, incoming %i) = %s", (held, incoming, partial) => {
    expect(looksPartial(held, incoming)).toBe(partial);
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

describe("venue checks", () => {
  const checks = () =>
    db
      .selectFrom("venueChecks")
      .select(["venueId", "status", "screenings", "message"])
      .orderBy("venueId")
      .orderBy("checkedAt")
      .execute();

  it("logs each venue of a batch once: ok with screenings, empty without", async () => {
    const b = batch([screening("1")]);
    b.venues.push({ ...b.venues[0]!, id: "testchain:venue:9", sourceId: "9", name: "Tyhjä" });
    await ingestBatch(db, b);
    await ingestBatch(db, b); // the same files ingested again add nothing
    expect(await checks()).toEqual([
      { venueId: "testchain:venue:1", status: "ok", screenings: 1, message: null },
      { venueId: "testchain:venue:9", status: "empty", screenings: 0, message: null },
    ]);
  });

  it("logs an incomplete batch as partial, with its warnings", async () => {
    await ingestBatch(
      db,
      batch([screening("1")], {
        warnings: [{ code: "invalid-row", message: "4 screening rows not understood" }],
      }),
    );
    expect(await checks()).toEqual([
      {
        venueId: "testchain:venue:1",
        status: "partial",
        screenings: 1,
        message: "4 screening rows not understood",
      },
    ]);
  });

  it("logs a failed pull's venues from pull-status, once", async () => {
    await ingestBatch(db, batch([screening("1")]));
    const failed = {
      provider: "testchain",
      attemptedAt: later(FETCHED_AT, 24),
      status: "failed" as const,
      error: "Request failed with status code 503",
      durationMs: 900,
    };
    expect(await ingestPullStatus(db, [failed])).toBe(1);
    expect(await ingestPullStatus(db, [failed])).toBe(0);
    // An ok line logs nothing: its batch logs itself.
    expect(await ingestPullStatus(db, [{ ...failed, status: "ok" }])).toBe(0);
    expect((await checks()).map((c) => [c.status, c.message])).toEqual([
      ["ok", null],
      ["failed", "Request failed with status code 503"],
    ]);
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
