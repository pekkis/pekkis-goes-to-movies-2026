import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { IsohannuRawSnapshot } from "../../../src/providers/isohannu/fetch.ts";
import { filmIds, parseIsohannu } from "../../../src/providers/isohannu/parse.ts";
import { ISOHANNU_SITES } from "../../../src/providers/isohannu/sites.ts";

const SITE = ISOHANNU_SITES[0]!;
const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/isohannu", name), "utf8");
const HTML = fixture("isohannu-etusivu.html");
const snapshot = (overrides: Partial<IsohannuRawSnapshot> = {}): IsohannuRawSnapshot => ({
  fetchedAt: "2026-10-14T09:00:00.000Z",
  from: "2026-10-14",
  days: 7,
  html: HTML,
  films: {
    "2194": fixture("isohannu-leffasivu-2194.html"),
    "2111": fixture("isohannu-leffasivu-2111.html"),
  },
  ...overrides,
});

describe("parseIsohannu", () => {
  const batch = parseIsohannu(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (id: string) => batch.listings.find((l) => l.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "buy" });
    // Five rows; the private booking of a hall is not a screening.
    expect(batch.screenings).toHaveLength(5);
  });

  it("reads the day, hall, film id and the screening's own ticket link", () => {
    expect(show("124227")).toMatchObject({
      startsAt: "2026-10-14T16:00:00+03:00",
      businessDate: "2026-10-14",
      auditoriumId: "isohannu:screen:rauma-sali-1",
      listingId: "isohannu:film:2194",
      ticketUrl: "http://lipunmyynti.isohannu.fi/app/movies/2194/shows/124227/products/list.html",
      audio: ["fi"],
      subtitles: { kind: "unknown" },
    });
  });

  it("takes rating, runtime and genres from the film page", () => {
    expect(listing("2194")).toMatchObject({
      title: { fi: "KERRO KAIKILLE" },
      rating: "K-12",
      runtimeMinutes: 112,
      genres: ["Draama"],
    });
  });

  it("maps tag classes and version markers", () => {
    expect(show("124324").tags).toEqual(["last-screening"]);
    expect(show("124473")).toMatchObject({ tags: ["kids"], dubbed: true, audio: ["fi"] });
    expect(listing("2111")).toMatchObject({ title: { fi: "KÄTYRIT & MONSTERIT" }, rating: "K-7" });
  });

  it("reads several spoken languages", () => {
    const page = fixture("isohannu-leffasivu-2194.html").replace("suomi", "Ruotsi, Italia");
    const result = parseIsohannu(snapshot({ films: { "2194": page } }), SITE);
    expect(result.screenings.find((s) => s.sourceId === "124227")).toMatchObject({
      audio: ["sv", "it"],
      unmappedLabels: [],
    });
  });

  it("leaves a film without its page unknown, and an unknown tag flagged", () => {
    expect(listing("2142").rating).toBeUndefined();
    const tagged = HTML.replace("showtable-finalshow", "showtable-imax");
    const result = parseIsohannu(snapshot({ html: tagged }), SITE);
    expect(result.screenings.find((s) => s.sourceId === "124324")?.unmappedLabels).toEqual([
      "tag:imax",
    ]);
  });

  it("asks for the pages of the films in the window, but not of non-screenings", () => {
    expect(filmIds(HTML, SITE, "2026-10-14", 7)).toEqual(["2194", "2142", "2117", "2111"]);
    expect(filmIds(HTML, SITE, "2026-10-16", 7)).toEqual(["2111"]);
  });

  it("warns, without marking the batch incomplete, when a film page fails", () => {
    const result = parseIsohannu(snapshot({ films: { "2194": null } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["film-page-missing"]);
    expect(isIncomplete(result)).toBe(false);
    expect(result.screenings).toHaveLength(5);
  });

  it("warns about a day heading it cannot read", () => {
    const broken = HTML.replace("Torstai 15.10.2026", "Torstai");
    const result = parseIsohannu(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the show table is gone", () => {
    const result = parseIsohannu(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
