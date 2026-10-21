import { describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import { loadCityPage, loadVenuePage } from "../../src/lib/pages.ts";
import { pageHeaders } from "../../src/lib/headers.ts";
import { fakeFetch, screening, venue } from "../fixtures.ts";

const api = (pages: unknown[]) => {
  let n = 0;
  return fakeFetch({
    "/v1/venues": [venue(), venue({ id: "x:venue:2", city: "Tampere" })],
    "/v1/screenings": () => pages[n++],
  });
};

describe("loadCityPage", () => {
  it("asks for the city's screenings and follows every page", async () => {
    const fake = api([
      { date: "2026-10-13", items: [screening()], nextCursor: "abc" },
      { date: "2026-10-13", items: [screening({ id: "testchain:show:2" })], nextCursor: null },
    ]);
    const page = await loadCityPage(createApi("http://api", fake.impl), "jyvaskyla", "2026-10-13");
    expect(page?.city).toEqual({ name: "Jyväskylä", slug: "jyvaskyla" });
    expect(page?.venues.map((v) => v.id)).toEqual(["testchain:venue:1"]);
    expect(page?.screenings.map((s) => s.id)).toEqual(["testchain:show:1", "testchain:show:2"]);
    const asked = fake.requests.filter((u) => u.pathname === "/v1/screenings");
    expect(asked.map((u) => u.searchParams.get("city"))).toEqual(["Jyväskylä", "Jyväskylä"]);
    expect(asked[1]?.searchParams.get("cursor")).toBe("abc");
  });

  it("ignores a malformed date and uses the API's day", async () => {
    const fake = api([{ date: "2026-10-13", items: [], nextCursor: null }]);
    const page = await loadCityPage(createApi("http://api", fake.impl), "tampere", "31.2.");
    expect(page?.date).toBe("2026-10-13");
    expect(fake.requests.at(-1)?.searchParams.has("date")).toBe(false);
  });

  it("returns nothing for an unknown city", async () => {
    const fake = api([]);
    expect(await loadCityPage(createApi("http://api", fake.impl), "nowhere", null)).toBeUndefined();
  });
});

describe("loadVenuePage", () => {
  it("asks for the venue's screenings on the given day", async () => {
    const fake = api([{ date: "2026-10-14", items: [screening()], nextCursor: null }]);
    const page = await loadVenuePage(
      createApi("http://api", fake.impl),
      "kino-testi-jyvaskyla",
      "2026-10-14",
    );
    expect(page?.venue.id).toBe("testchain:venue:1");
    const asked = fake.requests.at(-1);
    expect(asked?.searchParams.get("venue")).toBe("testchain:venue:1");
    expect(asked?.searchParams.get("date")).toBe("2026-10-14");
  });

  it("returns nothing for an unknown venue", async () => {
    const fake = api([]);
    expect(
      await loadVenuePage(createApi("http://api", fake.impl), "kino-testi", null),
    ).toBeUndefined();
  });
});

describe("pageHeaders", () => {
  it("keeps search engines out unless indexing is on", () => {
    const off = new Headers({ "content-type": "text/html" });
    pageHeaders(off, { indexing: false });
    expect(off.get("x-robots-tag")).toBe("noindex, nofollow");
    expect(off.get("cache-control")).toBe("public, max-age=60");

    const on = new Headers({ "content-type": "text/html" });
    pageHeaders(on, { indexing: true });
    expect(on.has("x-robots-tag")).toBe(false);
  });

  it("limits what a page may do, and reports what the coming policy would block", () => {
    const headers = new Headers({ "content-type": "text/html" });
    pageHeaders(headers, { indexing: false });
    expect(headers.get("x-content-type-options")).toBe("nosniff");
    expect(headers.get("x-frame-options")).toBe("DENY");
    expect(headers.get("referrer-policy")).toBe("strict-origin-when-cross-origin");
    expect(headers.get("permissions-policy")).toContain("geolocation=(self)");
    expect(headers.get("content-security-policy-report-only")).toContain("frame-ancestors 'none'");
  });
});
