import { sql } from "kysely";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createApp } from "../../src/api/app.ts";
import { createDb } from "../../src/db/database.ts";
import { ingestBatch, ingestFilms } from "../../src/ingest/ingest.ts";
import { helsinkiToday } from "../../src/search/showtimes.ts";
import { batch, catalog, film, screening } from "../factory.ts";

const db = createDb(process.env["TEST_DATABASE_URL"]!);
const app = createApp({ db });

const get = async (path: string) => {
  const res = await app.request(path);
  return { status: res.status, headers: res.headers, body: (await res.json()) as any };
};

/** Screening ids without the `testchain:show:` prefix. */
const ids = (body: { items: { id: string }[] }) => body.items.map((s) => s.id.split(":").at(-1));

const HELSINKI = {
  id: "testchain:venue:2",
  provider: "testchain",
  sourceId: "2",
  name: "Pääkino",
  city: "Helsinki",
  geo: { lat: 60.17, lon: 24.94 },
};

beforeAll(async () => {
  await sql`truncate screenings, film_listings, auditoriums, venues, providers, films cascade`.execute(
    db,
  );
  await ingestFilms(db, catalog([film()]));
  const b = batch([
    screening("1"), // 18:00 Jyväskylä, tmdb:100
    screening("2", { startsAt: "2026-10-10T20:30:00+03:00" }),
    // After midnight, still on the 10th's programme.
    screening("3", { startsAt: "2026-10-11T00:30:00+03:00" }),
    screening("4", {
      venueId: HELSINKI.id,
      auditoriumId: undefined,
      startsAt: "2026-10-10T19:00:00+03:00",
    }),
    // An opera, not on TMDB.
    screening("5", {
      listingId: "testchain:film:opera",
      filmId: undefined,
      startsAt: "2026-10-10T19:30:00+03:00",
    }),
    screening("6", { businessDate: "2026-10-11", startsAt: "2026-10-11T18:00:00+03:00" }),
    screening("gone", { startsAt: "2026-10-10T21:00:00+03:00" }),
  ]);
  b.venues.push(HELSINKI);
  b.listings.push({
    id: "testchain:film:opera",
    provider: "testchain",
    sourceId: "opera",
    title: { fi: "Taikahuilu (Met Opera)" },
    runtimeMinutes: 190,
    genres: [],
    countries: [],
    kind: "event",
  });
  await ingestBatch(db, b);
  await db
    .updateTable("screenings")
    .set({ removedAt: new Date() })
    .where("sourceId", "=", "gone")
    .execute();
});

afterAll(() => db.destroy());

describe("meta", () => {
  it("reports health without caching", async () => {
    const res = await get("/v1/health");
    expect(res).toMatchObject({ status: 200, body: { ok: true, db: true } });
    expect(res.headers.get("cache-control")).toBe("no-store");
  });

  it("serves an OpenAPI document with every route", async () => {
    const { status, body } = await get("/openapi.json");
    expect(status).toBe(200);
    expect(Object.keys(body.paths).sort()).toEqual([
      "/v1/films/search",
      "/v1/films/{id}",
      "/v1/films/{id}/screenings",
      "/v1/health",
      "/v1/screenings",
      "/v1/venues",
      "/v1/venues/{id}",
    ]);
    expect(body.info.description).toMatch(/OpenStreetMap/);
  });

  it("answers unknown paths with JSON 404 and allows any origin", async () => {
    expect(await get("/v1/nope")).toMatchObject({ status: 404, body: { error: "not found" } });
    const res = await app.request("/v1/venues", { headers: { origin: "https://example.org" } });
    expect(res.headers.get("access-control-allow-origin")).toBe("*");
    expect(res.headers.get("cache-control")).toBe("public, max-age=60");
  });
});

describe("venues", () => {
  it("lists venues with coordinates and provider", async () => {
    const { body } = await get("/v1/venues");
    expect(body.map((v: { id: string }) => v.id)).toEqual([
      "testchain:venue:2",
      "testchain:venue:1",
    ]);
    expect(body[1]).toMatchObject({
      name: "Testikino",
      geo: { lat: 62.24, lon: 25.75 },
      provider: { id: "testchain", booking: "buy" },
    });
  });

  it("filters by viewport and city", async () => {
    const helsinki = await get("/v1/venues?bbox=24.5,60.1,25.3,60.4");
    expect(helsinki.body.map((v: { id: string }) => v.id)).toEqual([HELSINKI.id]);
    const city = await get("/v1/venues?city=jyväskylä");
    expect(city.body.map((v: { id: string }) => v.id)).toEqual(["testchain:venue:1"]);
  });

  it("rejects a malformed or inverted bbox", async () => {
    expect((await get("/v1/venues?bbox=1,2,3")).status).toBe(400);
    const inverted = await get("/v1/venues?bbox=25.3,60.4,24.5,60.1");
    expect(inverted).toMatchObject({ status: 400, body: { error: "invalid request" } });
  });

  it("returns one venue, or 404", async () => {
    expect((await get(`/v1/venues/${HELSINKI.id}`)).body).toMatchObject({ city: "Helsinki" });
    expect((await get("/v1/venues/nope:venue:1")).status).toBe(404);
  });
});

describe("screenings", () => {
  it("lists a day's screenings in start order, hiding removed ones", async () => {
    const { body } = await get("/v1/screenings?date=2026-10-10");
    expect(ids(body)).toEqual(["1", "4", "5", "2", "3"]);
    expect(body.nextCursor).toBeNull();
  });

  it("formats screenings with Helsinki times, venue and film", async () => {
    const { body } = await get("/v1/screenings?date=2026-10-10&venue=testchain:venue:1&limit=1");
    expect(body.items[0]).toMatchObject({
      startsAt: "2026-10-10T18:00:00+03:00",
      endsAt: "2026-10-10T20:00:00+03:00",
      businessDate: "2026-10-10",
      venue: { id: "testchain:venue:1", city: "Jyväskylä", geo: { lat: 62.24, lon: 25.75 } },
      auditorium: "Sali 1",
      film: {
        id: "tmdb:100",
        kind: "film",
        title: "Testielokuva",
        year: 2026,
        posterUrl: "https://image.tmdb.org/t/p/w500/poster.jpg",
      },
      audio: ["en"],
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      formats: ["imax"],
      price: null,
      ticketUrl: "https://tickets.example/1",
    });
  });

  it("shows unmatched listings as such", async () => {
    const { body } = await get("/v1/screenings?date=2026-10-10&film=testchain:film:opera");
    expect(body.items[0].film).toEqual({
      id: "testchain:film:opera",
      kind: "listing",
      isEvent: true,
      title: "Taikahuilu (Met Opera)",
      originalTitle: null,
      year: null,
      runtimeMinutes: 190,
      rating: null,
      posterUrl: null,
    });
  });

  it("keeps shows after midnight when filtering by start time", async () => {
    const { body } = await get("/v1/screenings?date=2026-10-10&after=19:30");
    expect(ids(body)).toEqual(["5", "2", "3"]);
  });

  it("filters by viewport and film", async () => {
    expect(
      ids((await get("/v1/screenings?date=2026-10-10&bbox=24.5,60.1,25.3,60.4")).body),
    ).toEqual(["4"]);
    expect(ids((await get("/v1/screenings?date=2026-10-10&film=tmdb:100")).body)).toEqual([
      "1",
      "4",
      "2",
      "3",
    ]);
  });

  it("pages with a cursor without gaps or repeats", async () => {
    const seen: string[] = [];
    let cursor: string | null = null;
    do {
      const query: string = `/v1/screenings?date=2026-10-10&limit=2${cursor ? `&cursor=${cursor}` : ""}`;
      const { body } = await get(query);
      seen.push(...(ids(body) as string[]));
      cursor = body.nextCursor;
    } while (cursor);
    expect(seen).toEqual(["1", "4", "5", "2", "3"]);
  });

  it("defaults to today in Helsinki and rejects bad parameters", async () => {
    expect((await get("/v1/screenings")).body.date).toBe(await helsinkiToday(db));
    expect((await get("/v1/screenings?date=10.10.2026")).status).toBe(400);
    expect((await get("/v1/screenings?after=25:00")).status).toBe(400);
    expect((await get("/v1/screenings?limit=0")).status).toBe(400);
    expect((await get("/v1/screenings?cursor=bm9wZQ")).body).toEqual({ error: "invalid cursor" });
  });
});

describe("films", () => {
  it("finds films by fuzzy title", async () => {
    const { body } = await get("/v1/films/search?q=testielokva");
    expect(body[0].film).toMatchObject({ id: "tmdb:100", kind: "film" });
    expect(body[0].score).toBeGreaterThan(0.5);
    expect((await get("/v1/films/search?q=x")).status).toBe(400);
  });

  it("returns a TMDB film with all titles and trailers", async () => {
    const { body } = await get("/v1/films/tmdb:100");
    expect(body).toMatchObject({
      id: "tmdb:100",
      kind: "film",
      tmdbId: 100,
      titles: { fi: "Testielokuva", en: "Test Film" },
      overview: { en: "A film for tests." },
      trailers: [{ site: "YouTube", key: "abc", name: "Trailer" }],
    });
  });

  it("returns an unmatched listing, or 404", async () => {
    expect((await get("/v1/films/testchain:film:opera")).body).toMatchObject({
      kind: "listing",
      isEvent: true,
      tmdbId: null,
    });
    expect((await get("/v1/films/tmdb:999")).status).toBe(404);
  });

  it("lists where a film plays on a day", async () => {
    const { body } = await get("/v1/films/tmdb:100/screenings?date=2026-10-10&after=20:00");
    expect(ids(body)).toEqual(["2", "3"]);
    expect((await get("/v1/films/tmdb:999/screenings")).status).toBe(404);
  });
});
