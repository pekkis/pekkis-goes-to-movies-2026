import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KinomaattiRawSnapshot } from "../../../src/providers/kinomaatti/fetch.ts";
import { parseKinomaatti } from "../../../src/providers/kinomaatti/parse.ts";
import { KINOMAATTI_SITES } from "../../../src/providers/kinomaatti/sites.ts";

const SITE = KINOMAATTI_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kinomaatti/kinojalasjarvi-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KinomaattiRawSnapshot> = {}): KinomaattiRawSnapshot => ({
  fetchedAt: "2026-10-16T06:00:00.000Z",
  from: "2026-10-16",
  days: 7,
  html: HTML,
  ...overrides,
});

describe("parseKinomaatti", () => {
  const batch = parseKinomaatti(snapshot(), SITE);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "info" });
    expect(batch.screenings).toHaveLength(7);
  });

  it("reads the time, the price, the format and the film page", () => {
    expect(batch.screenings[0]).toMatchObject({
      startsAt: "2026-10-16T16:30:00+03:00",
      price: { amountCents: 1200, currency: "EUR" },
      presentation: { dimension: "2d" },
      ticketUrl: expect.stringMatching(/^https:\/\/kinojalasjarvi\.fi\/elokuva\/[^/]+\/$/),
    });
  });

  it("reads the title without the age and format badges, and the age from its image", () => {
    const fighter = batch.listings.find((l) => l.sourceId === "street-fighter");
    expect(fighter).toMatchObject({ title: { fi: "Street Fighter" }, rating: "K-12" });
  });

  it("warns about a row whose weekday fits no date", () => {
    const broken = HTML.replace("perjantai, 16.10. klo", "torstai, 16.10. klo");
    const result = parseKinomaatti(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
