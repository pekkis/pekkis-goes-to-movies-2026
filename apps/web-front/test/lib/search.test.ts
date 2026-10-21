import { describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import { loadSearchPage, parseSearchParams } from "../../src/lib/search.ts";
import { fakeFetch, screening, venue } from "../fixtures.ts";

const TODAY = "2026-10-13";
const q = (query: string) => new URLSearchParams(query);

// Two cinemas in Tampere ~1 km apart, one in Nokia ~15 km west.
const VENUES = [
  venue({ id: "t:venue:plevna", name: "Plevna", city: "Tampere", geo: { lat: 61.5, lon: 23.76 } }),
  venue({ id: "t:venue:atlas", name: "Atlas", city: "Tampere", geo: { lat: 61.49, lon: 23.77 } }),
  venue({ id: "n:venue:nokia", name: "Kino Nokia", city: "Nokia", geo: { lat: 61.48, lon: 23.5 } }),
];
const at = (id: string, v: (typeof VENUES)[number], over = {}) =>
  screening({ id, venue: { id: v.id, name: v.name, city: v.city, geo: v.geo }, ...over });

describe("parseSearchParams", () => {
  it("defaults to today, 25 km, no place and no film", () => {
    expect(parseSearchParams(q(""), TODAY)).toEqual({ days: [TODAY], radiusKm: 25 });
  });

  it("ignores a film or city name longer than the API takes", () => {
    const long = "a".repeat(101);
    expect(parseSearchParams(q(`elokuva=${long}&kaupunki=${long}`), TODAY)).toEqual({
      days: [TODAY],
      radiusKm: 25,
    });
  });

  it("keeps only offered days, a known radius, coordinates in Finland and a real film name", () => {
    const params = parseSearchParams(
      q(
        "paiva=2026-10-15&paiva=2026-10-13&paiva=2026-10-15&paiva=2026-12-24&paiva=x" +
          "&sade=10&lat=61.5&lon=23.76&kaupunki=tampere&elokuva=%20Lapin%20sota%20",
      ),
      TODAY,
    );
    expect(params).toEqual({
      days: ["2026-10-13", "2026-10-15"],
      here: { lat: 61.5, lon: 23.76 },
      city: "tampere",
      radiusKm: 10,
      film: "Lapin sota",
    });
    expect(parseSearchParams(q("sade=15"), TODAY).radiusKm).toBe(15);
    expect(parseSearchParams(q("sade=200"), TODAY).radiusKm).toBe(200);
    expect(parseSearchParams(q("sade=7&lat=40&lon=23&elokuva=x"), TODAY)).toEqual({
      days: [TODAY],
      radiusKm: 25,
    });
  });
});

describe("loadSearchPage", () => {
  it("shows only the form until there is a place or a film", async () => {
    const fake = fakeFetch({ "/v1/venues": VENUES });
    const page = await loadSearchPage(createApi("http://api", fake.impl), q(""), TODAY);
    expect(page.state).toBe("start");
    expect(page.cities.map((c) => c.name)).toEqual(["Nokia", "Tampere"]);
    expect(page.dayOptions).toHaveLength(7);
    expect(fake.requests.map((u) => u.pathname)).toEqual(["/v1/venues"]);
  });

  it("path A: loads each day around the city's centre and keeps what is within the radius", async () => {
    const fake = fakeFetch({
      "/v1/venues": VENUES,
      "/v1/screenings": (url: URL) => ({
        date: url.searchParams.get("date"),
        items:
          url.searchParams.get("date") === "2026-10-14"
            ? [at("b", VENUES[1]!, { startsAt: "2026-10-14T18:00:00+03:00" })]
            : [at("a", VENUES[0]!), at("c", VENUES[2]!)],
        nextCursor: null,
      }),
    });
    const page = await loadSearchPage(
      createApi("http://api", fake.impl),
      q("kaupunki=tampere&sade=5&paiva=2026-10-13&paiva=2026-10-14"),
      TODAY,
    );
    expect(page.place).toMatchObject({ kind: "city", name: "Tampere" });
    // Nokia is outside 5 km even if the box reached it.
    expect(page.screenings.map((s) => s.id)).toEqual(["a", "b"]);
    expect(Object.keys(page.distances).toSorted()).toEqual(["t:venue:atlas", "t:venue:plevna"]);
    expect(page.distances["t:venue:plevna"]).toBeLessThan(1);
    // Who runs each venue, from the venue list, for grouping by provider.
    expect(page.providers["t:venue:plevna"]).toEqual({ id: "testchain", name: "Test Chain" });
    const asked = fake.requests.filter((u) => u.pathname === "/v1/screenings");
    expect(asked.map((u) => u.searchParams.get("date"))).toEqual(["2026-10-13", "2026-10-14"]);
    expect(asked[0]?.searchParams.get("bbox")).toMatch(/^[\d.]+,[\d.]+,[\d.]+,[\d.]+$/);
  });

  it("prefers a chosen city to an earlier location, and uses the location without one", async () => {
    const fake = fakeFetch({
      "/v1/venues": VENUES,
      "/v1/screenings": { date: TODAY, items: [], nextCursor: null },
    });
    const api = createApi("http://api", fake.impl);
    const both = await loadSearchPage(api, q("lat=61.48&lon=23.5&kaupunki=tampere"), TODAY);
    expect(both.place).toMatchObject({ kind: "city", name: "Tampere" });
    const here = await loadSearchPage(api, q("lat=61.48&lon=23.5&kaupunki="), TODAY);
    expect(here.place).toEqual({ kind: "here", point: { lat: 61.48, lon: 23.5 } });
  });

  it("path B: finds the film by name and loads its days nationwide", async () => {
    const lapin = { ...screening().film, id: "tmdb:7", title: "Lapin sota" };
    const fake = fakeFetch({
      "/v1/venues": VENUES,
      "/v1/films/search": [{ score: 1, film: lapin }],
      "/v1/films/tmdb:7/screenings": {
        date: TODAY,
        items: [at("x", VENUES[2]!)],
        nextCursor: null,
      },
    });
    const page = await loadSearchPage(
      createApi("http://api", fake.impl),
      q("elokuva=lapin+sota"),
      TODAY,
    );
    expect(page.state).toBe("results");
    expect(page.films.map((f) => f.title)).toEqual(["Lapin sota"]);
    expect(page.screenings.map((s) => s.id)).toEqual(["x"]);
    expect(page.distances).toEqual({});
    const search = fake.requests.find((u) => u.pathname === "/v1/films/search");
    expect(search?.searchParams.get("q")).toBe("lapin sota");
  });
});
