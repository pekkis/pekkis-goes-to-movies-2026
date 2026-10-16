import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { PajakkakinoRawSnapshot } from "../../../src/providers/pajakkakino/fetch.ts";
import { parsePajakkakino } from "../../../src/providers/pajakkakino/parse.ts";
import { PAJAKKAKINO_SITES } from "../../../src/providers/pajakkakino/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const SITE = PAJAKKAKINO_SITES[0]!;
const POSTS = () => loadFixture("pajakkakino", "pajakkakino-posts.json") as unknown[];
const snapshot = (overrides: Partial<PajakkakinoRawSnapshot> = {}): PajakkakinoRawSnapshot => ({
  fetchedAt: "2026-10-09T06:00:00.000Z",
  from: "2026-10-09",
  days: 14,
  posts: POSTS(),
  ...overrides,
});

describe("parsePajakkakino", () => {
  const batch = parsePajakkakino(snapshot(), SITE);
  const starts = (title: string) => {
    const listing = batch.listings.find((l) => l.title.fi === title)!;
    return batch.screenings.filter((s) => s.listingId === listing.id).map((s) => s.startsAt);
  };

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "reserve" });
  });

  it("skips the struck-through (cancelled) row and keeps the rest", () => {
    expect(starts("PIRJO I SVERIGE")).toEqual([
      "2026-10-09T19:00:00+03:00",
      "2026-10-11T19:00:00+03:00",
      "2026-10-12T16:00:00+03:00",
      "2026-10-14T18:00:00+03:00",
      "2026-10-19T18:00:00+03:00",
    ]);
  });

  it("reads rows without the date's last dot, the audio and the subtitles", () => {
    expect(starts("VERITYN VARJO")).toEqual(["2026-10-18T18:00:00+03:00"]);
    const show = batch.screenings.find((s) => s.startsAt === "2026-10-18T18:00:00+03:00")!;
    expect(show).toMatchObject({
      audio: ["en"],
      subtitles: { kind: "languages", languages: ["fi"] },
      ticketUrl: "https://www.pajakkakino.fi/verityn-varjo/",
    });
    expect(batch.listings.find((l) => l.title.fi === "VERITYN VARJO")).toMatchObject({
      runtimeMinutes: 117,
      rating: "K-12",
    });
  });

  it("warns about a row whose weekday fits no date", () => {
    const posts = POSTS().map((p) =>
      JSON.parse(JSON.stringify(p).replace("SU 11.10. KLO 19:00", "LA 11.10. KLO 19:00")),
    );
    const result = parsePajakkakino(snapshot({ posts }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  describe("Römppäviikot's rows", () => {
    // Pirjo's last row, rewritten the ways the film week's posts write theirs.
    const LAST = "MA 19.10. KLO 18:00";
    const variant = (row: string, title = "PIRJO I SVERIGE") =>
      parsePajakkakino(
        snapshot({
          posts: POSTS().map((p) =>
            JSON.parse(
              JSON.stringify(p)
                .replace(LAST, row)
                .replace('"PIRJO I SVERIGE"', JSON.stringify(title)),
            ),
          ),
        }),
        SITE,
      );
    const late = (result: ReturnType<typeof parsePajakkakino>) =>
      result.screenings.filter((s) => s.businessDate === "2026-10-19").map((s) => s.startsAt);

    it("reads two times on one row", () => {
      const result = variant("MA 19.10. KLO 16:30 &amp; 18:30");
      expect(result.warnings).toEqual([]);
      expect(late(result)).toEqual(["2026-10-19T16:30:00+03:00", "2026-10-19T18:30:00+03:00"]);
    });

    it("keeps a row whose note says the film starts", () => {
      const result = variant("MA 19.10. KLO 18:00 elokuva alkaa");
      expect(result.warnings).toEqual([]);
      expect(late(result)).toEqual(["2026-10-19T18:00:00+03:00"]);
    });

    it("skips a reading circle, a date without a time and a time still to come", () => {
      for (const row of [
        "MA 19.10. KLO 16:30 alkaen lukupiiri, tervetuloa lukemaan yhdessä Pajakkakinoon!",
        "MA 19.10.",
        "MA 19.10 KLO ? ilmoitetaan myöhemmin",
      ]) {
        const result = variant(row);
        expect(result.warnings).toEqual([]);
        expect(late(result)).toEqual([]);
      }
    });

    it("strips the film week and the reading-circle note from the title", () => {
      const result = variant(LAST, "RÖMPPÄVIIKOT: PIRJO I SVERIGE (ELOKUVA + LUKUPIIRI)");
      const listing = result.listings.find((l) => l.title.fi === "PIRJO I SVERIGE");
      expect(listing).toBeDefined();
      expect(result.screenings.find((s) => s.listingId === listing!.id)?.series).toEqual([
        "Römppäviikot",
      ]);
    });
  });
});
