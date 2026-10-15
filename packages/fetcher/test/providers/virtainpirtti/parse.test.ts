import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { VirtainPirttiRawSnapshot } from "../../../src/providers/virtainpirtti/fetch.ts";
import { parseVirtainPirtti } from "../../../src/providers/virtainpirtti/parse.ts";
import { VIRTAINPIRTTI_SITES } from "../../../src/providers/virtainpirtti/sites.ts";

const SITE = VIRTAINPIRTTI_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/virtainpirtti/virtainpirtti-ohjelmistossa.html"),
  "utf8",
);
const snapshot = (overrides: Partial<VirtainPirttiRawSnapshot> = {}): VirtainPirttiRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 14,
  html: HTML,
  ...overrides,
});

describe("parseVirtainPirtti", () => {
  const batch = parseVirtainPirtti(snapshot(), SITE);
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;
  const shows = (title: string) =>
    batch.screenings.filter((s) => s.listingId === listing(title).id);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.listings.map((l) => l.title.fi).toSorted()).toEqual([
      "Digger",
      "Kerro kaikille",
      "Late Lammas-elokuva: Hämäräpuuhissa",
      "Pirjo i Sverige",
      "Unohdettu saari",
    ]);
    expect(batch.screenings).toHaveLength(11);
  });

  it("reads the title, the rating and the runtime", () => {
    expect(listing("Kerro kaikille")).toMatchObject({ rating: "K-12", runtimeMinutes: 112 });
    expect(listing("Pirjo i Sverige")).toMatchObject({ rating: "S" });
  });

  it("gives Finnish subtitles to the starred rows only", () => {
    expect(shows("Kerro kaikille").map((s) => s.subtitles.kind)).toEqual([
      "languages",
      "unknown",
      "unknown",
      "languages",
    ]);
  });

  it("marks the dubbed print, the preview, and reads a row behind a zero-width space", () => {
    expect(shows("Unohdettu saari")[0]).toMatchObject({ audio: ["fi"], dubbed: true });
    expect(shows("Late Lammas-elokuva: Hämäräpuuhissa")[0]?.tags).toEqual(["preview"]);
    expect(shows("Digger").map((s) => s.startsAt)).toEqual(["2026-10-16T17:30:00+03:00"]);
  });

  it("warns about a row whose weekday fits no date", () => {
    const broken = HTML.replace("la 17.10. klo 17.00", "su 17.10. klo 17.00");
    const result = parseVirtainPirtti(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
