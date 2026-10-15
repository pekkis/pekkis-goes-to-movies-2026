import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { VaakunaRawSnapshot } from "../../../src/providers/vaakuna/fetch.ts";
import { parseVaakuna } from "../../../src/providers/vaakuna/parse.ts";
import { VAAKUNA_SITES } from "../../../src/providers/vaakuna/sites.ts";

const SITE = VAAKUNA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/vaakuna/vaakuna-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<VaakunaRawSnapshot> = {}): VaakunaRawSnapshot => ({
  fetchedAt: "2026-10-14T06:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseVaakuna", () => {
  const batch = parseVaakuna(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (id: string) => batch.listings.find((l) => l.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "reserve" });
    expect(batch.screenings).toHaveLength(6);
  });

  it("places a weekday-checked date, the price and the film page", () => {
    expect(show("rakkautta-ja-virtahepoja-202610201440")).toMatchObject({
      startsAt: "2026-10-20T14:40:00+03:00",
      price: { amountCents: 1300, currency: "EUR" },
      ticketUrl: "https://www.kinovaakuna.fi/elokuvat/rakkautta-ja-virtahepoja.html",
    });
    expect(listing("rakkautta-ja-virtahepoja")).toMatchObject({
      rating: "K-12",
      runtimeMinutes: 102,
    });
  });

  it("reads a version marker on the row", () => {
    expect(show("unohdettu-saari-202610141410")).toMatchObject({ dubbed: true, audio: ["fi"] });
  });

  it("reads a preview without a weekday, labels as tags", () => {
    expect(show("yon-lapsi-202610311930")).toMatchObject({
      startsAt: "2026-10-31T19:30:00+02:00",
      tags: ["preview", "premiere"],
    });
  });

  it("skips an opening day without a time", () => {
    const soon = HTML.replace(/Ti 20\.10\.\s+klo 14:40/, "Ensi-ilta 30.10.2026");
    const result = parseVaakuna(snapshot({ html: soon }), SITE);
    expect(result.warnings).toEqual([]);
    expect(result.screenings).toHaveLength(5);
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replace(/Ti 20\.10\.\s+klo 14:40/, "Ma 20.10. klo 14:40");
    const result = parseVaakuna(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the cards are gone", () => {
    const result = parseVaakuna(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
