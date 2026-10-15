import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { HaminaRawSnapshot } from "../../../src/providers/hamina/fetch.ts";
import { parseHamina } from "../../../src/providers/hamina/parse.ts";
import { HAMINA_SITES } from "../../../src/providers/hamina/sites.ts";

const SITE = HAMINA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/hamina/hamina-kino.html"),
  "utf8",
);
const snapshot = (overrides: Partial<HaminaRawSnapshot> = {}): HaminaRawSnapshot => ({
  fetchedAt: "2026-10-14T06:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseHamina", () => {
  const batch = parseHamina(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (key: string) => batch.listings.find((l) => l.sourceId === key)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(13);
  });

  it("reads the labelled fields, in either way of writing the runtime", () => {
    expect(listing("pirjo-i-sverige")).toMatchObject({
      title: { fi: "Pirjo i Sverige" },
      rating: "S",
      runtimeMinutes: 88,
    });
    expect(listing("unohdettu-saari")).toMatchObject({ rating: "K-7", runtimeMinutes: 109 });
  });

  it("uses the film's price, or the row's own for that showing", () => {
    expect(show("pirjo-i-sverige-202610152000").price).toEqual({
      amountCents: 1100,
      currency: "EUR",
    });
    expect(show("pirjo-i-sverige-202610221500").price).toEqual({
      amountCents: 800,
      currency: "EUR",
    });
  });

  it("reads the version by the page's own legend", () => {
    expect(show("unohdettu-saari-202610141700")).toMatchObject({ dubbed: true, audio: ["fi"] });
    const og = HTML.replace("DUB", "OG");
    const result = parseHamina(snapshot({ html: og }), SITE);
    expect(
      result.screenings.find((s) => s.sourceId === "unohdettu-saari-202610141700"),
    ).toMatchObject({
      dubbed: false,
      audio: [],
      subtitles: { kind: "languages", languages: ["fi"] },
    });
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replace(/Ke\s+14\.10\.\s+Klo\s+17:00/, "Ti 14.10. Klo 17:00");
    const result = parseHamina(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the film blocks are gone", () => {
    const result = parseHamina(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
