import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KinoVisioRawSnapshot } from "../../../src/providers/kinovisio/fetch.ts";
import { parseKinoVisio } from "../../../src/providers/kinovisio/parse.ts";
import { KINOVISIO_SITES } from "../../../src/providers/kinovisio/sites.ts";

const SITE = KINOVISIO_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/kinovisio/kinovisio-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<KinoVisioRawSnapshot> = {}): KinoVisioRawSnapshot => ({
  fetchedAt: "2026-10-30T06:00:00.000Z",
  from: "2026-10-30",
  days: 10,
  html: HTML,
  ...overrides,
});

describe("parseKinoVisio", () => {
  const batch = parseKinoVisio(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "reserve" });
    // Pe 30.10. (3), La 31.10. (5), To 5.11. (5) and Su 8.11. (6).
    expect(batch.screenings).toHaveLength(19);
    expect(batch.screenings.flatMap((s) => s.unmappedLabels)).toEqual([]);
  });

  it("reads the day, the time, the title and its age limit", () => {
    expect(show("rakkautta-ja-virtahepoja-202610301615")).toMatchObject({
      startsAt: "2026-10-30T16:15:00+02:00",
      ticketUrl: "https://www.kinovisio.net/",
    });
    expect(listing("Lapin sota")).toMatchObject({ rating: "K-16", kind: "film" });
  });

  it("reads the notes after the title through the label table", () => {
    expect(show("jarki-ja-tunteet-202610301930").tags).toContain("premiere");
    expect(show("verityn-varjo-202610311815").tags).toContain("last-screening");
    // "– huom! ikäraja (puhuttu suomeksi) -toiseksi viimeinen näytös!"
    expect(show("unohdettu-saari-202610311615")).toMatchObject({
      audio: ["fi"],
      dubbed: true,
      unmappedLabels: [],
    });
  });

  it("lists a talk with a filmmaker as an event with a guest", () => {
    expect(listing("KLAUS HÄRÖ – Keskustelu elokuvasta Ei koskaan yksin")).toMatchObject({
      kind: "event",
    });
    expect(show("klaus-haro-keskustelu-elokuvasta-ei-koskaan-yksin-202611051700").tags).toEqual([
      "guest",
    ]);
  });

  it("takes the film club's prefix off the title as its strand", () => {
    expect(show("wild-horse-nine-202611081400").series).toEqual(["Leffaklubi"]);
  });

  it("warns when a line is not understood", () => {
    // The site writes a no-break space after the time.
    const broken = HTML.replace(/16:15\s<a/, "kello neljä <a");
    const result = parseKinoVisio(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
