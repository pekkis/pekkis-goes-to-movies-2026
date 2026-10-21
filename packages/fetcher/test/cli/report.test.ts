import type { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import {
  batchReport,
  failureReport,
  progressReport,
  summaryReport,
  tookReport,
} from "../../src/cli/report.ts";
import { plain, type Paint } from "../../src/lib/paint.ts";

/** Marks each painted span: <yellow>…</yellow>, <red+bold>…</red+bold>. */
const tag: Paint = (format, text) => {
  const name = [format].flat().join("+");
  return `<${name}>${text}</${name}>`;
};

const batchOf = (overrides: Partial<ProviderBatch>) =>
  ({
    venues: [{}],
    listings: [{}, {}],
    screenings: [{ unmappedLabels: [] }, { unmappedLabels: ["tag:Puola"] }],
    warnings: [],
    ...overrides,
  }) as unknown as ProviderBatch;

describe("the pull report", () => {
  it("reads the same without colour", () => {
    expect(batchReport("kinoaurora", batchOf({}), plain)).toEqual([
      "kinoaurora: 1 venues, 2 films, 2 screenings, 0 warnings, unmapped labels: tag:Puola",
    ]);
  });

  it("paints data-missing warnings red, deliberate skips yellow", () => {
    const batch = batchOf({
      warnings: [
        { code: "invalid-row", message: "2 rows not understood" },
        { code: "venue-without-geo", message: "Pohjantähti has no coordinates" },
      ],
    });
    expect(batchReport("alatalo", batch, tag)).toEqual([
      "<bold>alatalo</bold>: 1 venues, 2 films, 2 screenings, <yellow>2 warnings</yellow>, <cyan>unmapped labels: tag:Puola</cyan>",
      "  <red>[invalid-row]</red> 2 rows not understood",
      "  <yellow>[venue-without-geo]</yellow> Pohjantähti has no coordinates",
    ]);
  });

  it("flags a provider with no screenings", () => {
    expect(batchReport("huvimylly", batchOf({ screenings: [] }), tag)[0]).toContain(
      "<yellow>0 screenings</yellow>",
    );
  });

  it("paints failures red and the summary by its outcome", () => {
    expect(failureReport("kinojalasjarvi", new Error("Request timed out"), tag)).toBe(
      "<bold>kinojalasjarvi</bold>: <red+bold>FAILED</red+bold>: Request timed out",
    );
    expect(summaryReport(102, 102, "data", tag)).toBe(
      "<green>pulled 102 of 102 providers</green> into data",
    );
    expect(summaryReport(101, 102, "data", tag)).toBe(
      "<red+bold>pulled 101 of 102 providers</red+bold> into data",
    );
  });
});

describe("progress", () => {
  it("names what a running pull is waiting for, longest first, a long wait in yellow", () => {
    const now = 1_000_000;
    const running = new Map([
      ["kinopirtti", now - 20_000],
      ["biosalo", now - 245_000],
    ]);
    expect(progressReport(71, 102, running, now, tag)).toBe(
      "<cyan>… 71 of 102 done</cyan>; running: <yellow>biosalo 4 min 05 s</yellow>, kinopirtti 20 s",
    );
    expect(progressReport(102, 102, new Map(), now, plain)).toBe("… 102 of 102 done");
  });

  it("says how long a provider took, a slow one in yellow", () => {
    expect(tookReport(12_400, tag)).toBe("(12 s)");
    expect(tookReport(65_000, tag)).toBe("<yellow>(1 min 05 s)</yellow>");
  });
});
