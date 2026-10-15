import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { JuliaRawSnapshot } from "../../../src/providers/julia/fetch.ts";
import { parseJulia } from "../../../src/providers/julia/parse.ts";
import { JULIA_SITES } from "../../../src/providers/julia/sites.ts";

const SITE = JULIA_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/julia/julia-ohjelmisto.html"),
  "utf8",
);
const snapshot = (overrides: Partial<JuliaRawSnapshot> = {}): JuliaRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseJulia", () => {
  const batch = parseJulia(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (id: string) => batch.listings.find((l) => l.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(8);
  });

  it("reads the two-digit year, the hall and the film page", () => {
    expect(show("1843-202610201700")).toMatchObject({
      startsAt: "2026-10-20T17:00:00+03:00",
      auditoriumId: "julia:screen:hyvinkaa-sali-2",
      ticketUrl: "https://juliaelokuvat.fi/elokuvat/pirjo-i-sverige/",
    });
  });

  it("reads the labelled facts", () => {
    expect(listing("1843")).toMatchObject({
      title: { fi: "Pirjo i Sverige" },
      rating: "S",
      runtimeMinutes: 88,
      genres: ["Komedia", "Kotimainen"],
      kind: "film",
    });
  });

  it("reads an opera as an event, with its runtime besides the intermission", () => {
    expect(listing("1838")).toMatchObject({
      title: { fi: "Don Giovanni (Vicenza festivaali / Mozart)" },
      runtimeMinutes: 175,
      kind: "event",
    });
    expect(show("1838-202610281300").tags).toEqual(["event-cinema"]);
  });

  it("marks a listing event cinema by its genre alone", () => {
    const plain = HTML.replace("Ooppera: Don Giovanni", "Don Giovanni");
    const result = parseJulia(snapshot({ html: plain }), SITE);
    expect(result.listings.find((l) => l.sourceId === "1838")?.kind).toBe("event");
  });

  it("warns about a row it cannot read", () => {
    const broken = HTML.replace("15.10.26 klo 16:00", "15.10. klo 16");
    const result = parseJulia(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the programme is gone", () => {
    const result = parseJulia(snapshot({ html: "<html><body></body></html>" }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
