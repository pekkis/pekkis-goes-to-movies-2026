import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { BioMarlonRawSnapshot } from "../../../src/providers/biomarlon/fetch.ts";
import { parseBioMarlon } from "../../../src/providers/biomarlon/parse.ts";
import { BIOMARLON_SITES } from "../../../src/providers/biomarlon/sites.ts";

const SITE = BIOMARLON_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/biomarlon/biomarlon-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<BioMarlonRawSnapshot> = {}): BioMarlonRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 14,
  html: HTML,
  ...overrides,
});

describe("parseBioMarlon", () => {
  const batch = parseBioMarlon(snapshot(), SITE);
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;
  const shows = (title: string) =>
    batch.screenings.filter((s) => s.listingId === listing(title).id);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    // Lapin sota and the coming films have no time yet; the private screening is skipped.
    expect(batch.listings.map((l) => l.title.fi).toSorted()).toEqual([
      "NÄÄ MAAT, NÄÄ MANNUT – MEIDÄN KAUHAJOKI",
      "PIKKU KUMMITUS LAPANEN KEPPOSTELEE",
      "PIRJO I SVERIGE",
      "UNOHDETTU SAARI",
    ]);
    expect(shows("NÄÄ MAAT, NÄÄ MANNUT – MEIDÄN KAUHAJOKI").map((s) => s.startsAt)).toEqual([
      "2026-10-21T18:00:00+03:00",
    ]);
  });

  it("reads the facts: rating, runtime and price", () => {
    expect(listing("PIRJO I SVERIGE")).toMatchObject({ rating: "S", runtimeMinutes: 85 });
    expect(listing("UNOHDETTU SAARI")).toMatchObject({ rating: "K-7", runtimeMinutes: 100 });
    expect(listing("PIKKU KUMMITUS LAPANEN KEPPOSTELEE")).toMatchObject({ runtimeMinutes: 60 });
    expect(shows("PIRJO I SVERIGE")[0]).toMatchObject({
      startsAt: "2026-10-15T17:00:00+03:00",
      price: { amountCents: 1400 },
    });
    expect(shows("NÄÄ MAAT, NÄÄ MANNUT – MEIDÄN KAUHAJOKI")[0]?.price).toMatchObject({
      amountCents: 0,
    });
  });

  it("marks the premiere and the Finnish-dubbed print", () => {
    expect(shows("PIKKU KUMMITUS LAPANEN KEPPOSTELEE").map((s) => s.tags)).toEqual([
      ["premiere"],
      [],
      [],
    ]);
    expect(shows("UNOHDETTU SAARI")[0]).toMatchObject({ audio: ["fi"], dubbed: true });
    expect(shows("PIRJO I SVERIGE")[0]?.dubbed).toBeUndefined();
  });

  it("warns about a row whose weekday fits no date", () => {
    const broken = HTML.replace("to 15.10. 17:00", "ke 15.10. 17:00");
    const result = parseBioMarlon(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
