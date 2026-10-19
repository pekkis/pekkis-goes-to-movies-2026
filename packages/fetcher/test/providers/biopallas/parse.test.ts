import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { BioPallasRawSnapshot } from "../../../src/providers/biopallas/fetch.ts";
import { parseBioPallas } from "../../../src/providers/biopallas/parse.ts";
import { BIOPALLAS_SITES } from "../../../src/providers/biopallas/sites.ts";

const SITE = BIOPALLAS_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/biopallas/biopallas-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<BioPallasRawSnapshot> = {}): BioPallasRawSnapshot => ({
  fetchedAt: "2026-10-13T06:00:00.000Z",
  from: "2026-10-13",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseBioPallas", () => {
  const batch = parseBioPallas(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch; the coming-soon dates are not screenings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.listings.map((l) => l.title.fi)).not.toContain("Lapin sota");
  });

  it("joins a date block to the title block before it and the price block after", () => {
    expect(show("other-mommy-202610141900")).toMatchObject({
      startsAt: "2026-10-14T19:00:00+03:00",
      price: { amountCents: 1300, currency: "EUR" },
    });
    expect(batch.listings.find((l) => l.sourceId === "other-mommy")).toMatchObject({
      rating: "K-16",
      runtimeMinutes: 93,
    });
  });

  it("skips a private booking listed as a title, without a warning (2026-10-19)", () => {
    const html = HTML.replaceAll("Other Mommy", "Yksityistilaisuus");
    const result = parseBioPallas(snapshot({ html }), SITE);
    expect(result.warnings).toEqual([]);
    expect(result.listings.map((l) => l.title.fi)).not.toContain("Yksityistilaisuus");
    expect(result.screenings).toHaveLength(
      batch.screenings.filter((s) => !s.sourceId.startsWith("other-mommy")).length,
    );
  });

  it("reads one amount with a description as the price", () => {
    expect(show("kerro-kaikille-202610131400").price).toEqual({
      amountCents: 1200,
      currency: "EUR",
    });
  });

  it("reads a version line between the title and the facts", () => {
    expect(show("bortglomda-on-202610151500")).toMatchObject({ dubbed: true, audio: ["sv"] });
  });

  it("publishes no price for two amounts", () => {
    const two = HTML.replace("<p>13€</p>", "<p>22/25€</p>");
    const result = parseBioPallas(snapshot({ html: two }), SITE);
    expect(
      result.screenings.find((s) => s.sourceId === "pirjo-i-sverige-202610131900")?.price,
    ).toBeUndefined();
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replace("<p>Ti 13.10</p>", "<p>Ma 13.10</p>");
    const result = parseBioPallas(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
