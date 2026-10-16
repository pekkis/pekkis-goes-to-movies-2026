import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KaarreRawSnapshot } from "../../../src/providers/kaarre/fetch.ts";
import { parseKaarre } from "../../../src/providers/kaarre/parse.ts";
import { KAARRE_SITES } from "../../../src/providers/kaarre/sites.ts";

const SITE = KAARRE_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kaarre/kaarre-elokuvat.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KaarreRawSnapshot> = {}): KaarreRawSnapshot => ({
  fetchedAt: "2026-10-07T06:00:00.000Z",
  from: "2026-10-07",
  days: 21,
  html: HTML,
  ...overrides,
});

describe("parseKaarre", () => {
  const batch = parseKaarre(snapshot(), SITE);
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;
  const shows = (title: string) =>
    batch.screenings.filter((s) => s.listingId === listing(title).id);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    // The film descriptions below the programme are not read again.
    expect(batch.screenings).toHaveLength(8);
  });

  it("reads rows with or without minutes, and the facts line", () => {
    expect(shows("HETKI ENNEN VALOA").map((s) => s.startsAt)).toEqual([
      "2026-10-07T18:30:00+03:00",
      "2026-10-09T18:00:00+03:00",
      "2026-10-11T18:00:00+03:00",
    ]);
    expect(listing("HETKI ENNEN VALOA")).toMatchObject({ rating: "K-7", runtimeMinutes: 87 });
    expect(listing("PIRJO I SVERIGE").rating).toBe("S");
    expect(shows("PIRJO I SVERIGE")[0]?.price).toMatchObject({ amountCents: 1000 });
  });

  it("marks the dub and the last screening", () => {
    const saari = shows("UNOHDETTU SAARI");
    expect(saari[0]).toMatchObject({ audio: ["fi"], dubbed: true });
    expect(saari.map((s) => s.tags)).toEqual([[], [], ["last-screening"]]);
  });

  it("warns about a row whose weekday fits no date", () => {
    const broken = HTML.replace("Pe 9.10. klo 18", "La 9.10. klo 18");
    const result = parseKaarre(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
