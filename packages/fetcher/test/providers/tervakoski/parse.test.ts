import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { TervakoskiRawSnapshot } from "../../../src/providers/tervakoski/fetch.ts";
import { parseTervakoski } from "../../../src/providers/tervakoski/parse.ts";
import { TERVAKOSKI_SITES } from "../../../src/providers/tervakoski/sites.ts";

const SITE = TERVAKOSKI_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/tervakoski/tervakoski-ohjelmisto.html"),
  "utf8",
);
const snapshot = (overrides: Partial<TervakoskiRawSnapshot> = {}): TervakoskiRawSnapshot => ({
  fetchedAt: "2026-10-14T06:00:00.000Z",
  from: "2026-10-14",
  days: 7,
  html: HTML,
  ...overrides,
});

describe("parseTervakoski", () => {
  const batch = parseTervakoski(snapshot(), SITE);
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings.map((s) => s.startsAt)).toEqual([
      "2026-10-14T17:00:00+03:00",
      "2026-10-14T19:00:00+03:00",
      "2026-10-15T17:00:00+03:00",
      "2026-10-15T19:15:00+03:00",
      "2026-10-16T17:00:00+03:00",
      "2026-10-16T18:30:00+03:00",
    ]);
  });

  it("reads the title, the rating, the runtime and the price from the row", () => {
    expect(listing("Pirjo i Sverige")).toMatchObject({ rating: "S", runtimeMinutes: 88 });
    expect(listing("Kerro kaikille")).toMatchObject({ rating: "K-12", runtimeMinutes: 112 });
    expect(batch.screenings[0]?.price).toMatchObject({ amountCents: 1000 });
    expect(batch.screenings[4]?.price).toMatchObject({ amountCents: 900 });
  });

  it("marks the Finnish-dubbed print", () => {
    const saari = batch.screenings.find((s) => s.listingId === listing("Unohdettu saari").id);
    expect(saari).toMatchObject({ audio: ["fi"], dubbed: true });
    expect(batch.screenings[0]?.dubbed).toBeUndefined();
  });

  it("skips a private event quietly, and reads a runtime after a stray comma (2026-10-17)", () => {
    const html = HTML.replace(
      /Klo 19\.00 &#8211;\s*<a href="#h-kerro-kaikille"[^>]*\s*>Kerro kaikille \(K12\),<\/a\s*>\s*Kotimainen, draama, kesto 1t 52 min/,
      "Klo 19.00 &#8211; Yksityistilaisuus</p><p>Klo 20.00 &#8211; Kerro kaikille (K12), kotimainen, kesto, 1t 52 min",
    );
    expect(html).not.toBe(HTML);
    const result = parseTervakoski(snapshot({ html }), SITE);
    expect(result.warnings).toEqual([]);
    expect(result.screenings.map((s) => s.startsAt)).toContain("2026-10-14T20:00:00+03:00");
    expect(result.screenings.map((s) => s.startsAt)).not.toContain("2026-10-14T19:00:00+03:00");
    expect(result.listings.find((l) => l.title.fi === "Kerro kaikille")?.runtimeMinutes).toBe(112);
  });

  it("warns about a day whose weekday fits no date", () => {
    const broken = HTML.replace("Keskiviikko 14.10.", "Tiistai 14.10.");
    const result = parseTervakoski(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
