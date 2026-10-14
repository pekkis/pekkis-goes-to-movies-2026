import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it, vi } from "vitest";
import { fetchEngel, type EngelRawSnapshot } from "../../../src/providers/engel/fetch.ts";
import { filmPages, parseEngel } from "../../../src/providers/engel/parse.ts";
import { ENGEL_SITES } from "../../../src/providers/engel/sites.ts";
import type { HttpClient } from "../../../src/lib/http.ts";

const SITE = ENGEL_SITES[0]!;
const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/engel", name), "utf8");
const HTML = fixture("engel-etusivu.html");
const ROSE_URL = "https://kinoengel.fi/elokuva/rose/";
const ROSE = fixture("engel-elokuva-rose.html");
const snapshot = (overrides: Partial<EngelRawSnapshot> = {}): EngelRawSnapshot => ({
  fetchedAt: "2026-10-14T09:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  html: HTML,
  films: { [ROSE_URL]: ROSE },
  ...overrides,
});

describe("parseEngel", () => {
  const batch = parseEngel(snapshot(), SITE);
  const at = (startsAt: string) => batch.screenings.find((s) => s.startsAt === startsAt)!;
  const titleOf = (s: { listingId: string }) =>
    batch.listings.find((l) => l.id === s.listingId)!.title.fi;

  it("produces a valid batch without warnings, each screening once", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ id: "kinoengel", platform: "custom", booking: "buy" });
    // 18 rows: the page repeats 14.10.
    expect(batch.screenings).toHaveLength(15);
  });

  it("dates rows by their day block and links the film's page", () => {
    const grazia = at("2026-10-14T18:30:00+03:00");
    expect(titleOf(grazia)).toBe("La Grazia");
    expect(grazia).toMatchObject({
      businessDate: "2026-10-14",
      sourceId: "la-grazia-202610141830",
      ticketUrl: "https://kinoengel.fi/elokuva/la-grazia/",
    });
  });

  it('skips "coming soon" entries, which have a day but no time', () => {
    expect(batch.screenings.some((s) => s.businessDate === "2026-10-30")).toBe(false);
  });

  it("takes runtime, spoken language and subtitles from the film page", () => {
    const rose = at("2026-10-14T21:00:00+03:00");
    expect(rose).toMatchObject({
      audio: ["de"],
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
    });
    const listing = batch.listings.find((l) => l.id === rose.listingId)!;
    // The age limit is not read: the page says it is not known yet, whatever its class.
    expect(listing).toMatchObject({ title: { fi: "Rose" }, runtimeMinutes: 94 });
    expect(listing.rating).toBeUndefined();
    expect(listing.originalTitle).toBeUndefined();
  });

  it('reads "Ei tekstitystä" as no subtitles', () => {
    const page = ROSE.replace("Suomi-Ruotsi", "Ei tekstitystä");
    const result = parseEngel(snapshot({ films: { [ROSE_URL]: page } }), SITE);
    const rose = result.screenings.find((s) => s.startsAt === "2026-10-14T21:00:00+03:00");
    expect(rose?.subtitles).toEqual({ kind: "none" });
  });

  it("asks for the film pages of the screenings in the window only", () => {
    expect(filmPages(HTML, SITE, "2026-10-14", 1)).toEqual([
      "https://kinoengel.fi/elokuva/autofiktio/",
      "https://kinoengel.fi/elokuva/la-grazia/",
      ROSE_URL,
    ]);
  });

  it("keeps the screenings when a film page fails, and says so", () => {
    const result = parseEngel(snapshot({ films: { [ROSE_URL]: null } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["film-page-missing"]);
    expect(isIncomplete(result)).toBe(false);
    expect(result.screenings).toHaveLength(15);
  });

  it("reads the Barnsöndagar strand", () => {
    const laban = at("2026-10-18T13:00:00+03:00");
    expect(titleOf(laban)).toBe("Lilla spöket Laban busar vidare");
    expect(laban).toMatchObject({ series: ["Barnsöndagar"], tags: ["kids"] });
  });

  it("refuses a row whose shown day contradicts its block", () => {
    const wrong = HTML.replace("Ke 14.10.", "Ke 15.10.");
    const result = parseEngel(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the schedule is gone", () => {
    const result = parseEngel(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});

describe("fetchEngel", () => {
  const http = (html: string): HttpClient => ({
    getJson: vi.fn(),
    getText: vi.fn(async () => html),
  });

  it("fails on a captcha challenge instead of parsing it", async () => {
    await expect(
      fetchEngel(http("<html>sgcaptcha challenge</html>"), SITE, { from: "2026-10-14", days: 7 }),
    ).rejects.toThrow(/captcha/);
  });

  it("returns the page otherwise", async () => {
    const raw = await fetchEngel(http(HTML), SITE, { from: "2026-10-14", days: 1 });
    expect(raw.html).toBe(HTML);
    expect(Object.keys(raw.films)).toHaveLength(3);
  });
});
