import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KinoKuvaRawSnapshot } from "../../../src/providers/kinokuva/fetch.ts";
import { parseKinoKuva } from "../../../src/providers/kinokuva/parse.ts";
import { KINOKUVA_SITES } from "../../../src/providers/kinokuva/sites.ts";

const SITE = KINOKUVA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kinokuva/kinokuva-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KinoKuvaRawSnapshot> = {}): KinoKuvaRawSnapshot => ({
  fetchedAt: "2026-10-14T06:00:00.000Z",
  from: "2026-10-14",
  days: 14,
  html: HTML,
  ...overrides,
});

describe("parseKinoKuva", () => {
  const batch = parseKinoKuva(snapshot(), SITE);
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;
  const shows = (title: string) =>
    batch.screenings.filter((s) => s.listingId === listing(title).id);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(6);
  });

  it("reads the rows, the runtime, the rating and the price", () => {
    expect(shows("KERRO KAIKILLE").map((s) => s.startsAt)).toEqual([
      "2026-10-14T19:00:00+03:00",
      "2026-10-17T16:00:00+03:00",
      "2026-10-20T19:00:00+03:00",
    ]);
    expect(listing("KERRO KAIKILLE")).toMatchObject({ runtimeMinutes: 112, rating: "K-12" });
    expect(shows("KERRO KAIKILLE")[0]?.price).toMatchObject({ amountCents: 1400 });
  });

  it("splits two times on one day and marks the previews", () => {
    const late = shows("LATE LAMMAS -ELOKUVA: HÄMÄRÄPUUHISSA");
    expect(late.map((s) => s.startsAt)).toEqual([
      "2026-10-15T14:00:00+03:00",
      "2026-10-15T17:00:00+03:00",
    ]);
    expect(late.every((s) => s.tags.includes("preview"))).toBe(true);
  });

  it("reads the strand, free entry and the subtitle language", () => {
    expect(shows("JUNAT - TRAINS")[0]).toMatchObject({
      series: ["Puolan elokuvaviikot"],
      price: { amountCents: 0 },
      subtitles: { kind: "languages", languages: ["en"] },
    });
  });

  it("reads a label before the day and a note after the time (2026-11-02)", () => {
    const labelled = HTML.replace("KE 14.10. KLO 19.00", "ENSI-ILTA KE 14.10. KLO 19.00")
      .replace("LA 17.10. KLO 16.00", "LA 17.10. KLO 16.00 leffa-kaffinäytös!")
      .replace("TI 20.10. KLO 19.00", "TI 20.10. KLO 19.00 juhlanäytös");
    const result = parseKinoKuva(snapshot({ html: labelled }), SITE);
    expect(result.warnings).toEqual([]);
    const kerro = result.screenings.filter((s) => s.listingId.endsWith(":film:kerro-kaikille"));
    expect(kerro.map((s) => [s.startsAt, s.tags, s.unmappedLabels])).toEqual([
      ["2026-10-14T19:00:00+03:00", ["premiere"], []],
      ["2026-10-17T16:00:00+03:00", [], []],
      ["2026-10-20T19:00:00+03:00", [], ["note:juhlanäytös"]],
    ]);
  });

  it("warns about a row whose weekday fits no date", () => {
    const broken = HTML.replace("KE 14.10. KLO 19.00", "MA 14.10. KLO 19.00");
    const result = parseKinoKuva(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
