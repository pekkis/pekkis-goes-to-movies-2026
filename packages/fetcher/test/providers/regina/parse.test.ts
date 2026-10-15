import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it, vi } from "vitest";
import type { HttpClient } from "../../../src/lib/http.ts";
import { fetchRegina, type ReginaRawSnapshot } from "../../../src/providers/regina/fetch.ts";
import { parseRegina } from "../../../src/providers/regina/parse.ts";
import { REGINA_SITES } from "../../../src/providers/regina/sites.ts";

const SITE = REGINA_SITES[0]!;
const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/regina", name), "utf8");
const SCHEDULE = fixture("regina-schedule.html");
const CASABLANCA = fixture("regina-elokuva-121177.html");
const snapshot = (overrides: Partial<ReginaRawSnapshot> = {}): ReginaRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  schedule: SCHEDULE,
  films: { "121177": CASABLANCA },
  ...overrides,
});

describe("parseRegina", () => {
  const batch = parseRegina(snapshot(), SITE);
  const casablanca = batch.listings.find((l) => l.sourceId === "121177")!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "buy" });
    expect(batch.screenings).toHaveLength(3);
  });

  it("reads the row's start and copies KAVI's ticket link", () => {
    expect(batch.screenings[0]).toMatchObject({
      startsAt: "2026-10-15T17:30:00+03:00",
      listingId: casablanca.id,
      ticketUrl: "https://kauppa.kavi.fi/fi/events/pwdg/event_buybox/show/6a9e9e148de2654e478b4567",
    });
  });

  it("takes year, runtime, countries, subtitles, theme, print and rating from the film page", () => {
    expect(casablanca).toMatchObject({
      title: { fi: "CASABLANCA" },
      year: 1942,
      runtimeMinutes: 102,
      countries: ["Yhdysvallat"],
      rating: "S",
    });
    expect(batch.screenings[0]).toMatchObject({
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      series: ["INGRID BERGMAN"],
      presentation: { projection: "35mm" },
    });
  });

  it("keeps the screenings when a film page fails, and says so", () => {
    const result = parseRegina(snapshot({ films: { "121177": null } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["film-page-missing"]);
    expect(isIncomplete(result)).toBe(false);
    expect(result.screenings).toHaveLength(3);
  });

  it("warns about a row without a readable start", () => {
    const broken = SCHEDULE.replace("15-10-2026 17:30", "15.10. 17:30");
    const result = parseRegina(snapshot({ schedule: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
  });
});

describe("fetchRegina", () => {
  it("POSTs the start date as a form field, then reads each film page by GET", async () => {
    const http: HttpClient = {
      getJson: vi.fn(),
      getText: vi.fn(async () => CASABLANCA),
      postForm: vi.fn(async () => SCHEDULE),
    };
    const raw = await fetchRegina(http, SITE, { from: "2026-10-15", days: 31 });
    expect(http.postForm).toHaveBeenCalledWith(SITE.schedule, { getShowtimesMovies: "2026-10-15" });
    expect(Object.keys(raw.films).toSorted()).toEqual(["113634", "121177", "204052"]);
  });
});
