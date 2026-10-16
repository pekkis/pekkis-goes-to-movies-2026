import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KinoRioRawSnapshot } from "../../../src/providers/kinorio/fetch.ts";
import { parseKinoRio } from "../../../src/providers/kinorio/parse.ts";
import { KINORIO_SITES } from "../../../src/providers/kinorio/sites.ts";

const SITE = KINORIO_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kinorio/kinorio-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KinoRioRawSnapshot> = {}): KinoRioRawSnapshot => ({
  fetchedAt: "2026-10-16T06:00:00.000Z",
  from: "2026-10-16",
  days: 7,
  html: HTML,
  ...overrides,
});

describe("parseKinoRio", () => {
  const batch = parseKinoRio(snapshot(), SITE);
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;
  const shows = (title: string) =>
    batch.screenings.filter((s) => s.listingId === listing(title).id);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.listings.map((l) => l.title.fi).toSorted()).toEqual([
      "DIGGER",
      "Heart of the Beast",
      "Pikku Kummitus Lapanen keppostelee",
    ]);
  });

  it("reads the rows and the facts written beside them", () => {
    expect(shows("DIGGER").map((s) => s.startsAt)).toEqual([
      "2026-10-16T18:30:00+03:00",
      "2026-10-18T13:45:00+03:00",
      "2026-10-19T19:00:00+03:00",
      "2026-10-21T19:15:00+03:00",
    ]);
    expect(listing("DIGGER")).toMatchObject({ runtimeMinutes: 128, rating: "K-12" });
    expect(shows("DIGGER")[0]?.price).toMatchObject({ amountCents: 1500 });
  });

  it("reads a price row without a date, and the Finnish-dubbed note", () => {
    expect(shows("Heart of the Beast")).toHaveLength(2);
    expect(shows("Heart of the Beast")[0]?.price).toMatchObject({ amountCents: 1500 });
    expect(shows("Pikku Kummitus Lapanen keppostelee")[0]).toMatchObject({
      audio: ["fi"],
      dubbed: true,
    });
  });

  it("warns about a row whose weekday fits no date", () => {
    const broken = HTML.replace("Pe 16.10. klo 18.30", "La 16.10. klo 18.30");
    const result = parseKinoRio(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
