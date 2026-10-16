import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { SuojaRawSnapshot } from "../../../src/providers/suoja/fetch.ts";
import { parseSuoja } from "../../../src/providers/suoja/parse.ts";
import { SUOJA_SITES } from "../../../src/providers/suoja/sites.ts";

const SITE = SUOJA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/suoja/suoja-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<SuojaRawSnapshot> = {}): SuojaRawSnapshot => ({
  fetchedAt: "2026-10-16T06:00:00.000Z",
  from: "2026-10-16",
  days: 30,
  html: HTML,
  ...overrides,
});

describe("parseSuoja", () => {
  const batch = parseSuoja(snapshot(), SITE);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "buy" });
    // Kojootti 2, Kerro kaikille 1 (its 23.11. is past the window), Lapin sota 6; the
    // mobile copy of each list is not read again.
    expect(batch.screenings).toHaveLength(9);
  });

  it("uses the screening's id and copies its page as the ticket link", () => {
    expect(batch.screenings[0]).toMatchObject({
      sourceId: "2456",
      startsAt: "2026-10-16T19:00:00+03:00",
      ticketUrl: "https://suojanelokuvat.fi/naytos/2456",
    });
    expect(batch.listings.map((l) => l.sourceId).toSorted()).toEqual([
      "kerro-kaikille",
      "kojootti-vs-acme",
      "lapin-sota",
    ]);
  });

  it("warns about a showtime whose weekday fits no date", () => {
    const broken = HTML.replace('class="soon1 ajax"> pe 16.10.', 'class="soon1 ajax"> la 16.10.');
    const result = parseSuoja(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
