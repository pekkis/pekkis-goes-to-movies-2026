import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import { parseVista } from "../../../src/providers/vista/parse.ts";
import type { VistaRawSnapshot } from "../../../src/providers/vista/raw.ts";
import { VISTA_SITES } from "../../../src/providers/vista/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const SITE = VISTA_SITES[0]!;
const schedule = () =>
  loadFixture("vista", "korjaamo-schedule.json") as { Shows: Record<string, unknown>[] };
const snapshot = (overrides: Partial<VistaRawSnapshot> = {}): VistaRawSnapshot => ({
  fetchedAt: "2026-10-14T09:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  schedules: { "1007": schedule() },
  ...overrides,
});

describe("parseVista: Korjaamo Kino", () => {
  const batch = parseVista(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ id: "korjaamo", platform: "vista-public" });
    expect(batch.screenings).toHaveLength(4);
  });

  it("reads UTC times, the cinema's own programme day and its ticket link", () => {
    expect(show("168068")).toMatchObject({
      startsAt: "2026-10-15T10:00:00+03:00",
      businessDate: "2026-10-15",
      ticketUrl: "https://korjaamokino.fi/websales/show/168068",
      audio: ["en"],
      series: ["Kirjastokino"],
      subtitles: { kind: "unknown" },
    });
  });

  it("strips series prefixes, whatever their case", () => {
    expect(show("168074").series).toEqual(["Tekijätorstai"]);
    const titles = batch.listings.map((l) => l.title.fi);
    expect(titles).toContain("Misery");
    expect(titles).toContain("Kerro Kaikille");
  });

  it('leaves "useita kieliä" (several languages) as unknown audio, unflagged', () => {
    expect(show("168082")).toMatchObject({ audio: [], unmappedLabels: [] });
  });

  it("warns about a theatre no venue owns", () => {
    const edited = schedule();
    edited.Shows[0]!["TheatreID"] = 9999;
    const result = parseVista(snapshot({ schedules: { "1007": edited } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["unclaimed-venue"]);
  });

  it("keeps only shows inside the window", () => {
    const week = parseVista(snapshot({ days: 4 }), SITE);
    expect(week.screenings.map((s) => s.sourceId)).toEqual(["168068", "168074", "168081"]);
  });
});

describe("parseVista: Riviera (XML)", () => {
  const RIVIERA = VISTA_SITES.find((s) => s.provider === "riviera")!;
  const XML = readFileSync(
    join(import.meta.dirname, "../../fixtures/vista/riviera-schedule.xml"),
    "utf8",
  );
  const batch = parseVista(snapshot({ schedules: { all: XML } }), RIVIERA);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listingOf = (id: string) => batch.listings.find((l) => l.id === show(id).listingId)!;

  it("produces a valid batch without warnings, split by theatre", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.screenings).toHaveLength(6);
    expect(show("988254").venueId).toBe("riviera:venue:kallio");
    expect(show("988267")).toMatchObject({
      venueId: "riviera:venue:punavuori",
      auditoriumId: "riviera:screen:punavuori-sali-2",
    });
  });

  it("reads XML shows like JSON ones: times, languages and the http ticket link", () => {
    expect(show("988254")).toMatchObject({
      startsAt: "2026-10-14T18:00:00+03:00",
      businessDate: "2026-10-14",
      audio: ["en"],
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      ticketUrl: "http://tickets.rivieracinemas.fi/websales/show/988254/",
      unmappedLabels: [],
    });
    // Riviera's ProductionYear is the release year, so it is not used.
    expect(listingOf("988254")).toMatchObject({ runtimeMinutes: 109 });
    expect(listingOf("988254").year).toBeUndefined();
  });

  it('reads "K16/13" as K-16 and "(none)" as unknown', () => {
    expect(listingOf("988254").rating).toBe("K-16");
    expect(listingOf("988267").rating).toBe("K-12");
    expect(listingOf("988259").rating).toBeUndefined();
    expect(show("988259").unmappedLabels).toEqual([]);
  });

  it("strips series prefixes and a trailing year, which is the film's year", () => {
    // ProductionYear says 2026: the re-release.
    expect(listingOf("985246")).toMatchObject({
      title: { fi: "Paholainen pukeutuu Pradaan" },
      year: 2006,
    });
    expect(listingOf("985246").originalTitle).toBeUndefined();
    expect(show("985246").series).toEqual(["Leffabrunssi"]);
    expect(show("985149").tags).toEqual(["baby"]);
  });

  it('reads a hall named "-" (Bio-Kaari) as no auditorium', () => {
    const dashed = XML.replace(
      "<TheatreAuditorium>Sali 2</TheatreAuditorium>",
      "<TheatreAuditorium>-</TheatreAuditorium>",
    );
    const result = parseVista(snapshot({ schedules: { all: dashed } }), RIVIERA);
    expect(result.screenings.find((s) => s.sourceId === "988267")?.auditoriumId).toBeUndefined();
    expect(result.auditoriums.map((a) => a.name)).not.toContain("-");
  });

  it("leaves audio unknown when the show names no language", () => {
    expect(show("988565")).toMatchObject({ audio: [], subtitles: { kind: "unknown" } });
  });

  it("warns when the answer is not a schedule", () => {
    const result = parseVista(snapshot({ schedules: { all: "<html></html>" } }), RIVIERA);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
