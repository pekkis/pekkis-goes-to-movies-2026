import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { TmbRawSnapshot } from "../../../src/providers/tmb/fetch.ts";
import { parseTmb } from "../../../src/providers/tmb/parse.ts";
import { TMB_SITES } from "../../../src/providers/tmb/sites.ts";

const html = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/tmb", name), "utf8");
const site = (provider: string) => TMB_SITES.find((s) => s.provider === provider)!;

const snapshot = (name: string, overrides: Partial<TmbRawSnapshot> = {}): TmbRawSnapshot => ({
  fetchedAt: "2026-10-13T17:40:00.000Z",
  from: "2026-10-13",
  days: 90,
  html: html(name),
  ...overrides,
});

const byFilm = (batch: ProviderBatch, filmId: string) =>
  batch.screenings.filter((s) => s.listingId.endsWith(`:film:${filmId}`));

describe("parseTmb: Kino-Toijala", () => {
  const batch = parseTmb(snapshot("toijala-lista.html"), site("kinotoijala"));
  const listing = (filmId: string) => batch.listings.find((l) => l.sourceId === filmId)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({
      id: "kinotoijala",
      platform: "tmb",
      booking: "reserve",
    });
  });

  it("reads each dated, timed row as a screening; date-only announcements are skipped", () => {
    expect(batch.screenings).toHaveLength(7);
    expect(byFilm(batch, "879")).toEqual([]); // "23.10.2026": no weekday, no time
  });

  it("reads Helsinki time, links to the film's public page, never to ?varaa=", () => {
    expect(byFilm(batch, "867")[0]).toMatchObject({
      startsAt: "2026-10-14T13:30:00+03:00",
      businessDate: "2026-10-14",
      ticketUrl: "https://toijalan-kino.info/?ohjelmisto=867",
      tags: ["preview"],
      availability: "unknown",
    });
    expect(byFilm(batch, "867")[0]!.sourceId).toBe("867-202610141330");
  });

  it("strips labels in parentheses and prefixes, by the shared and site rules", () => {
    expect(listing("867").title.fi).toBe("Late Lammas -elokuva: Hämäräpuuhissa");
    expect(listing("866").title.fi).toBe("Pikkuli ja Tähtipeura");
    expect(byFilm(batch, "866")[0]!.tags).toEqual(["preview"]);
    expect(listing("840")).toMatchObject({ kind: "event" });
    expect(listing("841")).toMatchObject({
      kind: "event",
      title: { fi: expect.stringMatching(/^Pähkinänsärkijä/) },
    });
    expect(byFilm(batch, "878")[0]!.series).toEqual(["Akaan elokuvajuhla"]);
  });

  it("maps rating images; _0 means unrated, anything unknown is reported", () => {
    expect(listing("847").rating).toBe("S");
    expect(listing("867").rating).toBe("K-7");
    expect(listing("846").rating).toBe("K-16");
    expect(listing("878").rating).toBeUndefined();
    expect(byFilm(batch, "878")[0]!.unmappedLabels).toEqual(["ikaraja:5"]);
  });

  it("keeps only rows inside the window", () => {
    const week = parseTmb(snapshot("toijala-lista.html", { days: 7 }), site("kinotoijala"));
    expect(week.screenings.map((s) => s.businessDate).every((d) => d <= "2026-10-19")).toBe(true);
    expect(week.screenings).toHaveLength(4);
  });
});

describe("parseTmb: KinoMania", () => {
  const batch = parseTmb(snapshot("mania-lista.html"), site("kinomania"));

  it("reads halls where the site prints them", () => {
    expect(batch.warnings).toEqual([]);
    expect(batch.auditoriums.map((a) => a.name)).toEqual(["Sali 1", "Sali 2"]);
    expect(batch.screenings[0]).toMatchObject({
      auditoriumId: "kinomania:screen:pieksamaki-1",
      sourceId: expect.stringMatching(/-202610141745-1$/),
    });
  });
});

describe("parseTmb robustness", () => {
  it("warns when the page is not the list view, so ingest infers no removals", () => {
    const batch = parseTmb(
      snapshot("toijala-lista.html", { html: "<html><body>Huoltokatko</body></html>" }),
      site("kinotoijala"),
    );
    expect(batch.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
    expect(batch.screenings).toEqual([]);
  });

  it("skips a row whose weekday contradicts its date", () => {
    const broken = html("toijala-lista.html").replace("KE&nbsp;14.10.2026", "PE&nbsp;14.10.2026");
    const batch = parseTmb(snapshot("toijala-lista.html", { html: broken }), site("kinotoijala"));
    expect(batch.warnings.map((w) => w.code)).toEqual(["invalid-start"]);
  });
});
