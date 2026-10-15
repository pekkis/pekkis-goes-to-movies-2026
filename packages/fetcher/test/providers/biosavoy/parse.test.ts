import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { BioSavoyRawSnapshot } from "../../../src/providers/biosavoy/fetch.ts";
import { parseBioSavoy } from "../../../src/providers/biosavoy/parse.ts";
import { BIOSAVOY_SITES } from "../../../src/providers/biosavoy/sites.ts";

const SITE = BIOSAVOY_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/biosavoy/biosavoy-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<BioSavoyRawSnapshot> = {}): BioSavoyRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseBioSavoy", () => {
  const batch = parseBioSavoy(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "reserve" });
    expect(batch.screenings).toHaveLength(8);
  });

  it("takes the start from the ISO attribute and the hall from the block", () => {
    expect(show("bortglomda-202610151800")).toMatchObject({
      startsAt: "2026-10-15T18:00:00+03:00",
      auditoriumId: "biosavoy:screen:maarianhamina-sal-1",
      ticketUrl: "http://www.biosavoy.ax/film/bortglomda",
    });
    expect(batch.auditoriums.map((a) => a.name).toSorted()).toEqual(["Sal 1", "Sal 2"]);
  });

  it("keeps the Swedish title as Swedish", () => {
    expect(batch.listings.find((l) => l.sourceId === "bortglomda")?.title).toEqual({
      sv: "BORTGLÖMDA ÖN",
    });
  });

  it("warns about a row without a time", () => {
    const broken = HTML.replace('content="2026-10-15T18:00:00+03:00"', 'content=""');
    const result = parseBioSavoy(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the blocks are gone", () => {
    const result = parseBioSavoy(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
