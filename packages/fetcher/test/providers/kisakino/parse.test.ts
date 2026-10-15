import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KisaKinoRawSnapshot } from "../../../src/providers/kisakino/fetch.ts";
import { filmUrls, parseKisaKino } from "../../../src/providers/kisakino/parse.ts";
import { KISAKINO_SITES } from "../../../src/providers/kisakino/sites.ts";

const SITE = KISAKINO_SITES[0]!;
const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, `../../fixtures/kisakino/${name}`), "utf8");
const FRONT = fixture("kisakino-etusivu.html");
const FILM = fixture("kisakino-lapin-sota.html");
const URL = "https://kisakino.fi/elokuvat/lapin-sota/";
const snapshot = (overrides: Partial<KisaKinoRawSnapshot> = {}): KisaKinoRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  front: FRONT,
  films: { [URL]: FILM },
  ...overrides,
});

describe("parseKisaKino", () => {
  const batch = parseKisaKino(snapshot(), SITE);

  it("finds every film the front page links, once", () => {
    expect(filmUrls(FRONT, SITE)).toEqual([
      "https://kisakino.fi/elokuvat/presidentin-kyyditys/",
      URL,
      "https://kisakino.fi/elokuvat/rakkautta-ja-virtahepoja/",
    ]);
  });

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    // Every screening on the film page, not just the three the front page shows.
    expect(batch.screenings).toHaveLength(10);
  });

  it("reads the date, the time, the price and the film", () => {
    expect(batch.screenings[0]).toMatchObject({
      sourceId: "lapin-sota-202610241600",
      startsAt: "2026-10-24T16:00:00+03:00",
      price: { amountCents: 1200, currency: "EUR" },
      ticketUrl: URL,
    });
    // After the clocks go back.
    expect(batch.screenings.at(-1)?.startsAt).toBe("2026-11-05T18:00:00+02:00");
    expect(batch.listings).toEqual([
      expect.objectContaining({ title: { fi: "Lapin sota" }, runtimeMinutes: 158, rating: "K-16" }),
    ]);
  });

  it("warns about a weekday that does not fit the date", () => {
    const broken = FILM.replace("<strong>La</strong> 24.10.2026", "<strong>Su</strong> 24.10.2026");
    const result = parseKisaKino(snapshot({ films: { [URL]: broken } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(result.screenings).toHaveLength(9);
  });

  it("marks the batch incomplete when a film page fails", () => {
    const result = parseKisaKino(snapshot({ films: { [URL]: null } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-film-page"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
