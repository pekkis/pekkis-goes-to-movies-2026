import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vite-plus/test";
import type { KinoYlariRawSnapshot } from "../../../src/providers/kinoylari/fetch.ts";
import { parseKinoYlari } from "../../../src/providers/kinoylari/parse.ts";
import { KINOYLARI_SITES } from "../../../src/providers/kinoylari/sites.ts";

const SITE = KINOYLARI_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kinoylari/kinoylari-elokuvat.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KinoYlariRawSnapshot> = {}): KinoYlariRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseKinoYlari", () => {
  const batch = parseKinoYlari(snapshot(), SITE);
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;
  const shows = (title: string) =>
    batch.screenings.filter((s) => s.listingId === listing(title).id);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(18);
  });

  it("reads the programme list only, and the announcement does not double a row", () => {
    // The teaser above the list (2.12.) is not read; 23.10. is listed twice.
    expect(shows("Lapin sota").map((s) => s.startsAt)).toEqual([
      "2026-10-23T19:00:00+03:00",
      "2026-10-25T18:00:00+02:00", // after the clocks go back
    ]);
  });

  it("reads the title and the rating; K? is not rated yet", () => {
    expect(listing("Kätyrit & Monsterit").rating).toBe("K-7");
    expect(listing("Ryhmä Hau: Dinoelokuva").rating).toBe("S");
    expect(listing("Osasto Savukoski partisaanien jäljillä").rating).toBeUndefined();
    expect(batch.screenings.flatMap((s) => s.unmappedLabels)).toEqual([]);
  });

  it("warns about a row whose weekday fits no date", () => {
    const broken = HTML.replace("to 15.10. klo 15.00", "ke 15.10. klo 15.00");
    const result = parseKinoYlari(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  describe("the November 2026 layout: <p> rows without klo", () => {
    const html = readFileSync(
      join(import.meta.dirname, "../../fixtures/kinoylari/kinoylari-elokuvat-2026-11.html"),
      "utf8",
    );
    const result = parseKinoYlari(
      snapshot({ html, from: "2026-11-13", fetchedAt: "2026-11-13T06:00:00.000Z" }),
      SITE,
    );

    it("reads every row, and days without a film are no warning", () => {
      expect(() => ProviderBatch.parse(result)).not.toThrow();
      expect(result.warnings).toEqual([]);
      expect(result.screenings.map((s) => s.startsAt)).toEqual([
        "2026-11-13T19:00:00+02:00",
        "2026-11-14T16:00:00+02:00",
        "2026-11-14T18:00:00+02:00",
        "2026-11-21T18:00:00+02:00",
        "2026-11-28T18:00:00+02:00",
      ]);
      expect(result.listings.map((l) => l.title.fi)).toContain("Wicker - Intohimosta punottu");
    });

    it("warns about a dated line it cannot read instead of skipping it", () => {
      const broken = html.replace("16.00", "kello neljä");
      const r = parseKinoYlari(snapshot({ html: broken, from: "2026-11-13" }), SITE);
      expect(r.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    });
  });
});
