import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { LeviSummitRawSnapshot } from "../../../src/providers/levisummit/fetch.ts";
import { parseLeviSummit } from "../../../src/providers/levisummit/parse.ts";
import { LEVISUMMIT_SITES } from "../../../src/providers/levisummit/sites.ts";

const SITE = LEVISUMMIT_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/levisummit/levisummit-cinema.html"),
  "utf8",
);
const snapshot = (overrides: Partial<LeviSummitRawSnapshot> = {}): LeviSummitRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 7,
  html: HTML,
  ...overrides,
});

describe("parseLeviSummit", () => {
  const batch = parseLeviSummit(snapshot(), SITE);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "info" });
    expect(batch.screenings.map((s) => s.startsAt)).toEqual([
      "2026-10-15T14:00:00+03:00",
      "2026-10-15T17:00:00+03:00",
      "2026-10-16T14:00:00+03:00",
      "2026-10-16T17:00:00+03:00",
    ]);
  });

  it("reads the title, the adult price and the film page", () => {
    expect(batch.screenings[0]).toMatchObject({
      price: { amountCents: 1500, currency: "EUR" },
      ticketUrl: "https://www.kassiopeia.fi/levi-summit/cinema/ryhma-hau-dinoelokuva/",
    });
    expect(batch.listings.map((l) => l.title.fi).toSorted()).toEqual([
      "Rakkautta ja virtahepoja",
      "Ryhmä Hau: Dinoelokuva",
      "Verityn varjo",
    ]);
  });

  it("warns when a time's weekday is not the day's", () => {
    const broken = HTML.replace("To klo 14:00", "Pe klo 14:00");
    const result = parseLeviSummit(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
