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
  fetchedAt: "2026-11-01T06:00:00.000Z",
  from: "2026-11-01",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseNavetta", () => {
  const batch = parseNavetta(snapshot(), SITE);

  it("reads the film card's screening once, not the summary above it", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "reserve" });
    expect(batch.screenings).toHaveLength(1);
    expect(batch.screenings[0]).toMatchObject({
      sourceId: "lapin-sota-202611011700",
      startsAt: "2026-11-01T17:00:00+02:00",
      price: { amountCents: 1100, currency: "EUR" },
      ticketUrl: "https://www.navettakino.fi/varaa.php?id=80",
    });
  });

  it("reads the card's facts", () => {
    expect(batch.listings[0]).toMatchObject({
      title: { fi: "Lapin sota" },
      rating: "K-16",
      runtimeMinutes: 158,
    });
  });

  it("reads a facts line with the runtime in hours, and several screenings", () => {
    const changed = HTML.replace("K16, kesto 158 min", "Kesto 1 h 27 min, K12,").replace(
      ">Varaa</a></p>",
      ">Varaa</a></p><p>la 07.11 klo 15:00 - <a href='varaa.php?id=81'>Varaa</a></p>",
    );
    const result = parseNavetta(snapshot({ html: changed }), SITE);
    expect(result.warnings).toEqual([]);
    expect(result.listings[0]).toMatchObject({ rating: "K-12", runtimeMinutes: 87 });
    expect(result.screenings.map((s) => s.ticketUrl)).toEqual([
      "https://www.navettakino.fi/varaa.php?id=80",
      "https://www.navettakino.fi/varaa.php?id=81",
    ]);
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replace("su 01.11 klo 17:00", "la 01.11 klo 17:00");
    const result = parseNavetta(snapshot({ html: wrong }), SITE);
    expect(result.screenings).toEqual([]);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("reads a week without screenings as empty, without a warning (2026-11-03)", () => {
    const html =
      "<html><body><div class='w3-container w3-auto'><h2>Seuraavat näytökset</h2>" +
      "<p>Esitysajat ilmestyvät tälle sivulle aina alkuviikosta.</p></div></body></html>";
    const result = parseNavetta(snapshot({ html }), SITE);
    expect(result.screenings).toEqual([]);
    expect(result.warnings).toEqual([]);
  });

  it("warns when the page has neither the heading nor film cards", () => {
    const result = parseNavetta(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
