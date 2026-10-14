import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KuvakukkoRawSnapshot } from "../../../src/providers/kuvakukko/fetch.ts";
import { parseKuvakukko } from "../../../src/providers/kuvakukko/parse.ts";
import { KUVAKUKKO_SITES } from "../../../src/providers/kuvakukko/sites.ts";

const SITE = KUVAKUKKO_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kuvakukko/kuvakukko-ohjelmisto.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KuvakukkoRawSnapshot> = {}): KuvakukkoRawSnapshot => ({
  fetchedAt: "2026-10-14T09:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseKuvakukko", () => {
  const batch = parseKuvakukko(snapshot(), SITE);
  const at = (venue: string, startsAt: string) =>
    batch.screenings.find(
      (s) => s.venueId === `kuvakukko:venue:${venue}` && s.startsAt === startsAt,
    )!;
  const titleOf = (s: { listingId: string }) =>
    batch.listings.find((l) => l.id === s.listingId)!.title.fi;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.venues.map((v) => v.city)).toEqual(["Kuopio", "Nilsiä"]);
    expect(batch.screenings).toHaveLength(20);
  });

  it("reads days without a year and both ways of writing the time", () => {
    const first = at("kuopio", "2026-10-14T13:00:00+03:00");
    expect(titleOf(first)).toBe("Kerro kaikille");
    expect(first).toMatchObject({
      businessDate: "2026-10-14",
      ticketUrl: SITE.programme,
      sourceId: "kuopio-kerro-kaikille-202610141300",
    });
    expect(titleOf(at("kuopio", "2026-10-14T15:30:00+03:00"))).toBe(
      "The Secret Reading Club of Kabul",
    );
  });

  it("reads a day that starts mid-paragraph, after an empty line", () => {
    expect(titleOf(at("kuopio", "2026-10-16T14:00:00+03:00"))).toBe("Keltaiset kirjeet");
  });

  it("takes the first link with text, skipping an empty one", () => {
    expect(titleOf(at("kuopio", "2026-10-14T20:00:00+03:00"))).toBe("Digger");
  });

  it("drops notes in parentheses, closed or not", () => {
    expect(titleOf(at("kuopio", "2026-10-14T17:30:00+03:00"))).toBe("Sopeutumaton");
    expect(titleOf(at("kuopio", "2026-10-16T18:00:00+03:00"))).toBe(
      "Kuopion mediataidefestarit: Videoaktivistit – Kuopion videopaja 1985–1995",
    );
  });

  it("splits series prefixes", () => {
    const kuvi = at("kuopio", "2026-10-19T18:00:00+03:00");
    expect(titleOf(kuvi)).toBe("Omenaleikki");
    expect(kuvi.series).toEqual(["Kuvin aluesarja"]);
    expect(at("kuopio", "2026-10-22T17:30:00+03:00").series).toEqual(["Hyvät Kuvat -kerho"]);
  });

  it("files Manttu's past weekend under Nilsiä, outside the window", () => {
    const all = parseKuvakukko(snapshot({ from: "2026-10-09", days: 3 }), SITE);
    const nilsia = all.screenings.filter((s) => s.venueId === "kuvakukko:venue:nilsia");
    expect(nilsia.map((s) => s.startsAt)).toEqual([
      "2026-10-09T17:00:00+03:00",
      "2026-10-09T19:00:00+03:00",
    ]);
    expect(nilsia.map((s) => all.listings.find((l) => l.id === s.listingId)!.title.fi)).toEqual([
      "Rakkautta ja virtahepoja",
      "Kerro kaikille",
    ]);
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replace("Keskiviikko 14.10.", "Tiistai 14.10.");
    const result = parseKuvakukko(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual([
      "invalid-start",
      "invalid-row",
      "invalid-row",
      "invalid-row",
      "invalid-row",
    ]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when a cinema's heading is gone", () => {
    const result = parseKuvakukko(
      snapshot({ html: HTML.replace("Nilsiän Kino Mantun esitysaikataulu", "Nilsiä") }),
      SITE,
    );
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
