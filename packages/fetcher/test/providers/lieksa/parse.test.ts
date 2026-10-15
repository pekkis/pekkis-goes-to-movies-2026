import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { LieksaRawSnapshot } from "../../../src/providers/lieksa/fetch.ts";
import { parseLieksa } from "../../../src/providers/lieksa/parse.ts";
import { LIEKSA_SITES } from "../../../src/providers/lieksa/sites.ts";

const SITE = LIEKSA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/lieksa/lieksa-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<LieksaRawSnapshot> = {}): LieksaRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseLieksa", () => {
  const batch = parseLieksa(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch from the programme section only", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.listings.map((l) => l.title.fi).toSorted()).toEqual([
      "KERRO KAIKILLE",
      "OTHER MOMMY",
      "PIRJO I SVERIGE",
    ]);
    expect(batch.screenings).toHaveLength(7);
  });

  it("reads the price, runtime and the rating icon", () => {
    expect(batch.listings.find((l) => l.sourceId === "kerro-kaikille")).toMatchObject({
      rating: "K-12",
      runtimeMinutes: 112,
    });
    expect(show("kerro-kaikille-202610171500")).toMatchObject({
      startsAt: "2026-10-17T15:00:00+03:00",
      price: { amountCents: 1300, currency: "EUR" },
    });
  });

  it('reads "Tekstitetty" after the time as Finnish subtitles', () => {
    expect(show("kerro-kaikille-202610201300").subtitles).toEqual({
      kind: "languages",
      languages: ["fi"],
    });
  });

  it("flags a note it does not know", () => {
    const noted = HTML.replace("Tekstitetty", "Vauvakino");
    const result = parseLieksa(snapshot({ html: noted }), SITE);
    expect(
      result.screenings.find((s) => s.sourceId === "kerro-kaikille-202610201300")?.unmappedLabels,
    ).toEqual(["note:Vauvakino"]);
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replace(/La\s+17\.10\.\s+15\.00/, "Pe 17.10. 15.00");
    const result = parseLieksa(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the programme section is gone", () => {
    const result = parseLieksa(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
