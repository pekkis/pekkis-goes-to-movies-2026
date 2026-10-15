import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { MaritaRawSnapshot } from "../../../src/providers/marita/fetch.ts";
import { parseMarita } from "../../../src/providers/marita/parse.ts";
import { MARITA_SITES } from "../../../src/providers/marita/sites.ts";

const SITE = MARITA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/marita/marita-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<MaritaRawSnapshot> = {}): MaritaRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseMarita", () => {
  const batch = parseMarita(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(3);
  });

  it("reads the date with its year, the price, the language and the film page", () => {
    expect(show("pirjo-i-sverige-202610171600")).toMatchObject({
      startsAt: "2026-10-17T16:00:00+03:00",
      price: { amountCents: 1000, currency: "EUR" },
      audio: ["fi"],
      ticketUrl: "https://elokuvateatterimarita.fi/elokuva/pirjo-i-sverige/",
    });
  });

  it("reads the age image and ignores the content warnings beside it", () => {
    expect(batch.listings.find((l) => l.sourceId === "pirjo-i-sverige")?.rating).toBe("S");
    expect(batch.listings.find((l) => l.sourceId === "kerro-kaikille")?.rating).toBe("K-12");
    expect(batch.screenings.flatMap((s) => s.unmappedLabels)).toEqual([]);
  });

  it("publishes no price for two amounts", () => {
    const two = HTML.replace("Hinta: 10 €", "Hinta: 10/8 €");
    const result = parseMarita(snapshot({ html: two }), SITE);
    expect(
      result.screenings.find((s) => s.sourceId === "pirjo-i-sverige-202610171600")?.price,
    ).toBeUndefined();
  });

  it("warns about a block it cannot read", () => {
    const broken = HTML.replace("17.10.2026", "17.10.");
    const result = parseMarita(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the module is gone", () => {
    const result = parseMarita(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
