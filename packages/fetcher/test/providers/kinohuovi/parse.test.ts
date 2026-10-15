import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KinoHuoviRawSnapshot } from "../../../src/providers/kinohuovi/fetch.ts";
import { parseKinoHuovi } from "../../../src/providers/kinohuovi/parse.ts";
import { KINOHUOVI_SITES } from "../../../src/providers/kinohuovi/sites.ts";

const SITE = KINOHUOVI_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kinohuovi/kinohuovi-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KinoHuoviRawSnapshot> = {}): KinoHuoviRawSnapshot => ({
  fetchedAt: "2026-10-12T06:00:00.000Z",
  from: "2026-10-12",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseKinoHuovi", () => {
  const batch = parseKinoHuovi(snapshot(), SITE);
  const starts = (title: string) =>
    batch.screenings
      .filter((s) => batch.listings.find((l) => l.id === s.listingId)?.title.fi === title)
      .map((s) => s.startsAt);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
  });

  it("reads single dates and ranges proved by their weekdays", () => {
    expect(starts("KERRO KAIKILLE")).toEqual([
      "2026-10-12T18:00:00+03:00",
      "2026-10-18T18:00:00+03:00",
      "2026-10-19T18:00:00+03:00",
    ]);
    expect(starts("LAPIN SOTA")).toHaveLength(5);
  });

  it("reads runtime, price and the card's Dub.", () => {
    const pikkuli = batch.listings.find((l) => l.title.fi === "PIKKULI JA TÄHTIPEURA")!;
    expect(pikkuli.runtimeMinutes).toBe(80);
    expect(batch.screenings.find((s) => s.listingId === pikkuli.id)).toMatchObject({
      dubbed: true,
      audio: ["fi"],
      price: { amountCents: 1000, currency: "EUR" },
    });
  });

  it("places nothing when the weekdays do not fit the range", () => {
    const wrong = HTML.replace("PE, LA, SU, MA ja TI", "PE, LA, SU ja MA");
    const result = parseKinoHuovi(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the cards are gone", () => {
    const result = parseKinoHuovi(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
