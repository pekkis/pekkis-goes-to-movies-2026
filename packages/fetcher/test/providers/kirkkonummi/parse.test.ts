import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KirkkonummiRawSnapshot } from "../../../src/providers/kirkkonummi/fetch.ts";
import { parseKirkkonummi } from "../../../src/providers/kirkkonummi/parse.ts";
import { KIRKKONUMMI_SITES } from "../../../src/providers/kirkkonummi/sites.ts";

const SITE = KIRKKONUMMI_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kirkkonummi/kirkkonummi-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KirkkonummiRawSnapshot> = {}): KirkkonummiRawSnapshot => ({
  fetchedAt: "2026-10-14T06:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseKirkkonummi", () => {
  const batch = parseKirkkonummi(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch, each screening once although the page repeats every block", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "reserve" });
    expect(batch.screenings).toHaveLength(16);
  });

  it("reads full and short weekdays and two screenings on one row", () => {
    expect(show("matka-piemonteen-202610161800").startsAt).toBe("2026-10-16T18:00:00+03:00");
    expect(show("matka-piemonteen-202610181800")).toBeDefined();
    expect(show("matka-piemonteen-202610211830")).toBeDefined();
  });

  it("splits a Finnish / Swedish title", () => {
    expect(batch.listings.find((l) => l.sourceId === "matka-piemonteen")?.title).toEqual({
      fi: "Matka Piemonteen",
      sv: "Resan till Piemonte",
    });
  });

  it('reads "Puhumme suomea" under a film as dubbed into Finnish', () => {
    expect(show("kojootti-vs-acme-202610141300")).toMatchObject({ dubbed: true, audio: ["fi"] });
  });

  it("does not read an opening day as a screening", () => {
    expect(batch.listings.map((l) => l.title.fi)).not.toContain("LAPIN SOTA");
  });

  it("places nothing when the weekday does not fit the date", () => {
    const wrong = HTML.replaceAll("15.10. Torstai klo18.30", "15.10. Perjantai klo18.30");
    const result = parseKirkkonummi(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the page has no headings", () => {
    const result = parseKirkkonummi(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
