import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KurikanKinoRawSnapshot } from "../../../src/providers/kurikankino/fetch.ts";
import { parseKurikanKino } from "../../../src/providers/kurikankino/parse.ts";
import { KURIKANKINO_SITES } from "../../../src/providers/kurikankino/sites.ts";

const SITE = KURIKANKINO_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kurikankino/kurikankino-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KurikanKinoRawSnapshot> = {}): KurikanKinoRawSnapshot => ({
  fetchedAt: "2026-10-09T06:00:00.000Z",
  from: "2026-10-09",
  days: 14,
  html: HTML,
  ...overrides,
});

describe("parseKurikanKino", () => {
  const batch = parseKurikanKino(snapshot(), SITE);
  const listing = (key: string) => batch.listings.find((l) => l.sourceId === key)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "info" });
    // Two films with times (6 + 4), each printed twice; the coming-soon card adds none.
    expect(batch.screenings).toHaveLength(10);
    expect(batch.listings.map((l) => l.sourceId).toSorted()).toEqual([
      "ali-g-who-iz-i",
      "unohdettu-saari",
    ]);
  });

  it("reads the time from the stamp, the price and the film page", () => {
    expect(batch.screenings.find((s) => s.sourceId === "unohdettu-saari-1791572400")).toMatchObject(
      {
        startsAt: "2026-10-09T19:00:00+03:00",
        businessDate: "2026-10-09",
        price: { amountCents: 1300, currency: "EUR" },
        ticketUrl: "https://www.kurikankino.com/elokuvat/unohdettu-saari/",
      },
    );
  });

  it("reads the runtime and the age class into the listing", () => {
    expect(listing("unohdettu-saari")).toMatchObject({
      title: { fi: "Unohdettu Saari" },
      runtimeMinutes: 109,
      rating: "K-7",
    });
    expect(listing("ali-g-who-iz-i")).toMatchObject({ runtimeMinutes: 98, rating: "K-16" });
  });

  it("keeps only showtimes inside the window", () => {
    const later = parseKurikanKino(snapshot({ from: "2026-10-15", days: 7 }), SITE);
    expect(later.screenings.map((s) => s.startsAt)).toEqual([
      "2026-10-15T16:00:00+03:00",
      "2026-10-15T20:00:00+03:00",
    ]);
  });

  it("warns when the stamp and the printed time disagree", () => {
    const broken = HTML.replaceAll("pe 9.10. 19:00", "pe 9.10. 18:00");
    const result = parseKurikanKino(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
    expect(result.screenings).toHaveLength(9);
  });

  it("warns about a page with no film cards", () => {
    const result = parseKurikanKino(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
