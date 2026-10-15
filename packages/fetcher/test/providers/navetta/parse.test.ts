import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { NavettaRawSnapshot } from "../../../src/providers/navetta/fetch.ts";
import { parseNavetta } from "../../../src/providers/navetta/parse.ts";
import { NAVETTA_SITES } from "../../../src/providers/navetta/sites.ts";

const SITE = NAVETTA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/navetta/navetta-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<NavettaRawSnapshot> = {}): NavettaRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseNavetta", () => {
  const batch = parseNavetta(snapshot(), SITE);

  it("produces one screening although the page lists it twice", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(1);
    expect(batch.screenings[0]).toMatchObject({
      sourceId: "pirjo-i-sverige-202610171500",
      startsAt: "2026-10-17T15:00:00+03:00",
      price: { amountCents: 1000, currency: "EUR" },
    });
  });

  it("joins the film block's facts by title", () => {
    expect(batch.listings[0]).toMatchObject({
      title: { fi: "Pirjo i Sverige" },
      rating: "S",
      runtimeMinutes: 88,
    });
  });

  it("reads a facts line with the runtime in hours", () => {
    // Presidentin kyyditys has a block but no screening: its facts wait for one.
    const added = HTML.replace(
      "näytökset</strong></p>",
      "näytökset</strong></p>\n<p>Presidentin kyyditys la 17.10 klo 17:00</p>",
    );
    const result = parseNavetta(snapshot({ html: added }), SITE);
    expect(result.listings.find((l) => l.title.fi === "Presidentin kyyditys")).toMatchObject({
      rating: "K-12",
      runtimeMinutes: 87,
    });
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replaceAll("la 17.10 klo 15:00", "pe 17.10 klo 15:00");
    const result = parseNavetta(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the heading is gone", () => {
    const result = parseNavetta(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
