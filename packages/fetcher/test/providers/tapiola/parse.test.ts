import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { TapiolaRawSnapshot } from "../../../src/providers/tapiola/fetch.ts";
import { filmPages, parseTapiola } from "../../../src/providers/tapiola/parse.ts";
import { TAPIOLA_SITES } from "../../../src/providers/tapiola/sites.ts";

const SITE = TAPIOLA_SITES[0]!;
const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/tapiola", name), "utf8");
const LISTING = fixture("tapiola-elokuvat.html");
const RUN = "https://www.kinotapiola.fi/naytos";
const snapshot = (overrides: Partial<TapiolaRawSnapshot> = {}): TapiolaRawSnapshot => ({
  fetchedAt: "2026-10-14T09:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  listing: LISTING,
  films: {
    [`${RUN}/kojootti-vs-acme-dub/`]: fixture("tapiola-naytos-kojootti-dub.html"),
    [`${RUN}/tony-4/`]: fixture("tapiola-naytos-tony.html"),
  },
  ...overrides,
});

describe("parseTapiola", () => {
  const batch = parseTapiola(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ id: "kinotapiola", platform: "custom", booking: "buy" });
    // The opera on 13.12. is past the 31-day window.
    expect(batch.screenings).toHaveLength(5);
  });

  it("reads the date with its year and links the run's own page", () => {
    expect(show("tony-4-202610141945")).toMatchObject({
      startsAt: "2026-10-14T19:45:00+03:00",
      businessDate: "2026-10-14",
      ticketUrl: `${RUN}/tony-4/`,
      audio: ["en"],
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      unmappedLabels: [],
    });
  });

  it("treats every run of a title as one film, with the details of its page", () => {
    const tony = batch.listings.filter((l) => l.title.fi === "Tony");
    expect(tony).toHaveLength(1);
    expect(tony[0]).toMatchObject({ rating: "K-16", runtimeMinutes: 109 });
    expect(show("tony-5-202610171745")).toMatchObject({
      listingId: tony[0]!.id,
      audio: ["en"],
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
    });
  });

  it("keeps dubbed and original versions of one film apart", () => {
    expect(show("kojootti-vs-acme-dub-202610141500")).toMatchObject({
      dubbed: true,
      audio: ["fi"],
      // No subtitle box: unknown, not "none".
      subtitles: { kind: "unknown" },
    });
    expect(show("kojootti-vs-acme-orig-4-202610161500")).toMatchObject({ dubbed: false });
    expect(batch.listings.filter((l) => l.title.fi === "Kojootti vs. ACME")).toHaveLength(1);
  });

  it('leaves "OV" (original version) as unknown audio, unflagged', () => {
    const ov = fixture("tapiola-naytos-tony.html").replace("Englanti", "OV");
    const result = parseTapiola(snapshot({ films: { [`${RUN}/tony-4/`]: ov } }), SITE);
    expect(result.screenings.find((s) => s.sourceId === "tony-4-202610141945")).toMatchObject({
      audio: [],
      unmappedLabels: [],
    });
  });

  it("reads strands from the row's category class", () => {
    expect(show("maailman-rikkain-nainen-9-202610281500").tags).toEqual(["senior"]);
  });

  it("marks Royal Opera titles as event cinema", () => {
    const later = parseTapiola(snapshot({ days: 90 }), SITE);
    const carmen = later.listings.find((l) => l.title.fi === "Carmen")!;
    expect(carmen.kind).toBe("event");
    expect(later.screenings.find((s) => s.listingId === carmen.id)).toMatchObject({
      series: ["The Royal Opera"],
      tags: ["event-cinema"],
      ticketUrl: "https://www.kinotapiola.fi/ooppera-ja-baletti-naytos/the-royal-opera-carmen-2/",
    });
  });

  it("asks for one page per title in the window", () => {
    expect(filmPages(LISTING, SITE, "2026-10-14", 31)).toEqual([
      `${RUN}/kojootti-vs-acme-dub/`,
      `${RUN}/kojootti-vs-acme-orig-4/`,
      `${RUN}/maailman-rikkain-nainen-9/`,
      `${RUN}/tony-4/`,
    ]);
  });

  it("keeps the screenings when a page fails, and says so without marking the batch incomplete", () => {
    const result = parseTapiola(snapshot({ films: { [`${RUN}/tony-4/`]: null } }), SITE);
    expect(result.screenings).toHaveLength(5);
    expect(result.warnings.map((w) => w.code)).toEqual(["film-page-missing"]);
    expect(isIncomplete(result)).toBe(false);
    expect(result.listings.find((l) => l.title.fi === "Tony")?.rating).toBeUndefined();
  });

  it("warns, as missing data, about a block whose date it cannot read", () => {
    const broken = LISTING.replace("keskiviikko 14.10.2026 – Klo 19:45", "keskiviikko klo 19.45");
    const result = parseTapiola(snapshot({ listing: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the programme list is gone", () => {
    const result = parseTapiola(snapshot({ listing: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
