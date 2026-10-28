import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { BioSavoyRawSnapshot } from "../../../src/providers/biosavoy/fetch.ts";
import { filmUrls, parseBioSavoy } from "../../../src/providers/biosavoy/parse.ts";
import { BIOSAVOY_SITES } from "../../../src/providers/biosavoy/sites.ts";

const SITE = BIOSAVOY_SITES[0]!;
const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/biosavoy", name), "utf8");
const SCHEDULE = fixture("spelschema.html");
const LAPIN_SOTA = "https://www.biosavoy.ax/film/lapin-sota-lapplandskriget";
const PIKKULI = "https://www.biosavoy.ax/film/pikkuli-och-himmelshinden";
const FILMS = {
  [PIKKULI]: fixture("film-pikkuli-och-himmelshinden.html"),
  [LAPIN_SOTA]: fixture("film-lapin-sota-lapplandskriget.html"),
};
const snapshot = (overrides: Partial<BioSavoyRawSnapshot> = {}): BioSavoyRawSnapshot => ({
  fetchedAt: "2026-10-28T14:00:00.000Z",
  from: "2026-10-28",
  days: 7,
  schedule: SCHEDULE,
  films: FILMS,
  ...overrides,
});

describe("parseBioSavoy", () => {
  const batch = parseBioSavoy(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (slug: string) => batch.listings.find((l) => l.sourceId === slug)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "reserve" });
    // Pikkuli's 3 and Lapin sota's 6, of which 5.11 falls outside the seven days.
    expect(batch.screenings).toHaveLength(8);
  });

  it("finds the film pages on the schedule", () => {
    expect(filmUrls(SCHEDULE, SITE)).toEqual([PIKKULI, LAPIN_SOTA]);
  });

  it("takes each show's date, hall and price from the film page", () => {
    expect(show("lapin-sota-lapplandskriget-202610281930")).toMatchObject({
      startsAt: "2026-10-28T19:30:00+02:00",
      businessDate: "2026-10-28",
      auditoriumId: "biosavoy:screen:maarianhamina-sal-1",
      price: { amountCents: 1500, currency: "EUR" },
      ticketUrl: LAPIN_SOTA,
      subtitles: { kind: "unknown" },
    });
    expect(show("pikkuli-och-himmelshinden-202610281815")).toMatchObject({
      auditoriumId: "biosavoy:screen:maarianhamina-sal-2",
      price: { amountCents: 1300, currency: "EUR" },
    });
    expect(batch.auditoriums.map((a) => a.name).toSorted()).toEqual(["Sal 1", "Sal 2"]);
  });

  it("reads the age limit, Swedish T included, and the running time", () => {
    expect(listing("lapin-sota-lapplandskriget")).toMatchObject({
      title: { sv: "LAPIN SOTA (Lapplandskriget)" },
      rating: "K-16",
      runtimeMinutes: 155,
    });
    expect(listing("pikkuli-och-himmelshinden")).toMatchObject({ rating: "S", runtimeMinutes: 80 });
    expect(batch.screenings.flatMap((s) => s.unmappedLabels)).toEqual([]);
  });

  it("warns about a schedule row that no film page has", () => {
    const result = parseBioSavoy(snapshot({ films: { [PIKKULI]: FILMS[PIKKULI] } }), SITE);
    expect(result.warnings).toMatchObject([
      { code: "invalid-row", context: { rows: ["lapin-sota-lapplandskriget|28/10|19.30"] } },
    ]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns about a film page that failed", () => {
    const result = parseBioSavoy(snapshot({ films: { ...FILMS, [LAPIN_SOTA]: null } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-film-page", "invalid-row"]);
  });

  it("warns when the schedule is gone", () => {
    const result = parseBioSavoy(snapshot({ schedule: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
