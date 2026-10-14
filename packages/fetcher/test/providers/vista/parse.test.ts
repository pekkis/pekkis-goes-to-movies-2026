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
