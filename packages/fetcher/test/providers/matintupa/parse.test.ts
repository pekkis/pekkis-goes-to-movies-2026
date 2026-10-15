import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { MatinTupaRawSnapshot } from "../../../src/providers/matintupa/fetch.ts";
import { parseMatinTupa } from "../../../src/providers/matintupa/parse.ts";
import { MATINTUPA_SITES } from "../../../src/providers/matintupa/sites.ts";

const SITE = MATINTUPA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/matintupa/matintupa-ohjelmistossa.html"),
  "utf8",
);
const snapshot = (overrides: Partial<MatinTupaRawSnapshot> = {}): MatinTupaRawSnapshot => ({
  fetchedAt: "2026-10-13T06:00:00.000Z",
  from: "2026-10-13",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseMatinTupa", () => {
  const batch = parseMatinTupa(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (slug: string) => batch.listings.find((l) => l.sourceId === slug)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(9);
  });

  it("reads the screening lines and the labelled fields", () => {
    expect(show("pirjo-i-sverige-202610131920")).toMatchObject({
      startsAt: "2026-10-13T19:20:00+03:00",
      ticketUrl: "https://www.matin-tupa.fi/elokuvat/pirjo-i-sverige/",
    });
    expect(listing("pirjo-i-sverige")).toMatchObject({
      rating: "S",
      runtimeMinutes: 88,
      genres: ["Komedia", "Kotimainen"],
    });
  });

  it("publishes no price for an age band", () => {
    expect(show("pirjo-i-sverige-202610131920").price).toBeUndefined();
  });

  it('reads "Puhumme suomea" in the notes as dubbed, and the rating image', () => {
    expect(show("unohdettu-saari-202610131730")).toMatchObject({ dubbed: true, audio: ["fi"] });
    expect(listing("unohdettu-saari").rating).toBe("K-7");
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replace("ti 13.10. klo 19.20", "ma 13.10. klo 19.20");
    const result = parseMatinTupa(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the film blocks are gone", () => {
    const result = parseMatinTupa(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
