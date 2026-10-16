import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { BioDuxRawSnapshot } from "../../../src/providers/biodux/fetch.ts";
import { parseBioDux } from "../../../src/providers/biodux/parse.ts";
import { BIODUX_SITES } from "../../../src/providers/biodux/sites.ts";

const SITE = BIODUX_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/biodux/biodux-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<BioDuxRawSnapshot> = {}): BioDuxRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 14,
  html: HTML,
  ...overrides,
});

describe("parseBioDux", () => {
  const batch = parseBioDux(snapshot(), SITE);
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;
  const shows = (title: string) =>
    batch.screenings.filter((s) => s.listingId === listing(title).id);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    // Lapin sota has a date and no time yet.
    expect(batch.listings.some((l) => l.title.fi === "Lapin sota")).toBe(false);
    expect(batch.screenings).toHaveLength(13);
  });

  it("reads the title, the runtime and the closing age line", () => {
    expect(listing("Pirjo i Sverige")).toMatchObject({ runtimeMinutes: 88, rating: "S" });
    expect(shows("Kerro kaikille").map((s) => s.startsAt)).toEqual([
      "2026-10-17T19:00:00+03:00",
      "2026-10-18T16:30:00+03:00",
    ]);
  });

  it("splits a Finnish and Swedish title", () => {
    expect(listing("Matka Piemonteen")).toMatchObject({
      title: { fi: "Matka Piemonteen", sv: "Resan till Piemonte" },
      runtimeMinutes: 111,
    });
  });

  it("reads the languages: English with subtitles, and dubs per row", () => {
    expect(shows("Forgotten Island")[0]).toMatchObject({
      audio: ["en"],
      subtitles: { kind: "languages", languages: ["sv", "fi"] },
    });
    expect(shows("Bortglömda ön")[0]).toMatchObject({ audio: ["sv"], dubbed: true });
    expect(shows("Unohdettu saari")[0]).toMatchObject({ audio: ["fi"], dubbed: true });
    expect(listing("Unohdettu saari").rating).toBe("K-7");
  });

  it("warns about a row whose weekday fits no date", () => {
    const broken = HTML.replace("tor/to 15.10. 18.00", "fre/pe 15.10. 18.00");
    const result = parseBioDux(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
