import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KuvakukkoRawSnapshot } from "../../../src/providers/kuvakukko/fetch.ts";
import { filmPages, parseKuvakukko } from "../../../src/providers/kuvakukko/parse.ts";
import { KUVAKUKKO_SITES } from "../../../src/providers/kuvakukko/sites.ts";

const SITE = KUVAKUKKO_SITES[0]!;
const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/kuvakukko", name), "utf8");
const HTML = fixture("kuvakukko-ohjelmisto.html");
const PAGES = "https://www.kuvakukko.fi/ohjelmisto/kuvakukon-ja-kino-mantun-ohjelmisto";
/** Named after another film, holding La Grazia: the site reuses pages. */
const INVITE = `${PAGES}/the-invite/`;
const LA_GRAZIA = fixture("kuvakukko-elokuva-la-grazia.html");
const snapshot = (overrides: Partial<KuvakukkoRawSnapshot> = {}): KuvakukkoRawSnapshot => ({
  fetchedAt: "2026-10-14T09:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  html: HTML,
  films: { [INVITE]: LA_GRAZIA },
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

  it("takes year, runtime, age limit and languages from the film page its heading names", () => {
    const grazia = at("kuopio", "2026-10-15T13:00:00+03:00");
    expect(grazia).toMatchObject({
      audio: ["it"],
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      unmappedLabels: [],
    });
    expect(batch.listings.find((l) => l.id === grazia.listingId)).toMatchObject({
      title: { fi: "La Grazia" },
      year: 2025,
      runtimeMinutes: 133,
      rating: "K-7",
    });
  });

  it("flags an age limit outside the Finnish classes instead of publishing it", () => {
    const page = LA_GRAZIA.replace("• K7 •", "• K6 •");
    const result = parseKuvakukko(snapshot({ films: { [INVITE]: page } }), SITE);
    expect(() => ProviderBatch.parse(result)).not.toThrow();
    const grazia = result.listings.find((l) => l.title.fi === "La Grazia")!;
    expect(grazia.rating).toBeUndefined();
    expect(result.screenings.find((s) => s.listingId === grazia.id)?.unmappedLabels).toEqual([
      "rating:K6",
    ]);
  });

  it('reads "tekstitys: –" as unknown, unflagged', () => {
    const page = LA_GRAZIA.replace("tekstitys: suomi/ruotsi", "tekstitys: –");
    const result = parseKuvakukko(snapshot({ films: { [INVITE]: page } }), SITE);
    const grazia = result.listings.find((l) => l.title.fi === "La Grazia")!;
    expect(result.screenings.find((s) => s.listingId === grazia.id)).toMatchObject({
      subtitles: { kind: "unknown" },
      unmappedLabels: [],
    });
  });

  it("ignores a page whose heading names another film", () => {
    const kerro = `${PAGES}/kerro-kaikille/`;
    const result = parseKuvakukko(snapshot({ films: { [kerro]: LA_GRAZIA } }), SITE);
    const listing = result.listings.find((l) => l.title.fi === "Kerro kaikille")!;
    expect(listing.runtimeMinutes).toBeUndefined();
    expect(result.warnings).toEqual([]);
  });

  it("asks for each linked film page once, never an image", () => {
    const pages = filmPages(HTML, SITE, "2026-10-14", 31);
    expect(pages).toContain(INVITE);
    expect(new Set(pages).size).toBe(pages.length);
    expect(pages.some((p) => /\.jpe?g$/.test(p))).toBe(false);
  });

  it("keeps the screenings when a film page fails, and says so", () => {
    const result = parseKuvakukko(snapshot({ films: { [INVITE]: null } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["film-page-missing"]);
    expect(isIncomplete(result)).toBe(false);
    expect(result.screenings).toHaveLength(20);
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
