import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { OulunElokuvakeskusRawSnapshot } from "../../../src/providers/oulunelokuvakeskus/fetch.ts";
import { parseOulunElokuvakeskus } from "../../../src/providers/oulunelokuvakeskus/parse.ts";
import { OULUNELOKUVAKESKUS_SITES } from "../../../src/providers/oulunelokuvakeskus/sites.ts";

const SITE = OULUNELOKUVAKESKUS_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/oulunelokuvakeskus/ohjelma.html"),
  "utf8",
);
const snapshot = (
  overrides: Partial<OulunElokuvakeskusRawSnapshot> = {},
): OulunElokuvakeskusRawSnapshot => ({
  fetchedAt: "2026-10-30T06:00:00.000Z",
  from: "2026-10-30",
  days: 31,
  html: HTML,
  ...overrides,
});

describe("parseOulunElokuvakeskus", () => {
  const batch = parseOulunElokuvakeskus(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;

  it("produces a valid batch; closed days and the festival's block are not shows", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "buy" });
    expect(batch.screenings).toHaveLength(8);
  });

  it("reads a film's facts from its first table, the IMDb id included", () => {
    expect(listing("KELTAISET KIRJEET")).toMatchObject({
      originalTitle: "Gelbe Briefe",
      imdbId: "tt32888226",
      year: 2026,
      countries: ["Saksa", "Ranska", "Turkki"],
      runtimeMinutes: 128,
      rating: "K-12",
    });
    expect(show("keltaiset-kirjeet-202610301800")).toMatchObject({
      startsAt: "2026-10-30T18:00:00+02:00",
      price: { amountCents: 1100, currency: "EUR" },
      ticketUrl:
        "https://www.ticketmaster.fi/venue/studio-kulttuuritalo-valve-oulu-lippuja/vne/333",
    });
  });

  it("gives a later row without a date the date above it, and the film's facts", () => {
    expect(show("keltaiset-kirjeet-202610311830")).toMatchObject({
      price: { amountCents: 1100, currency: "EUR" },
    });
    expect(show("the-devils-202611011600").subtitles).toEqual({ kind: "none" });
  });

  it("reads a series heading above the director", () => {
    expect(show("me-ollaan-parhaita-202611031630")).toMatchObject({
      series: ["KUUKAUDEN POHJOISMAINEN ELOKUVA"],
      price: { amountCents: 700, currency: "EUR" },
    });
  });

  it("takes a matinee's prefix and its group price off a later row", () => {
    expect(show("berliinin-sankari-202611181430")).toMatchObject({
      labels: [{ source: "title.prefix", text: "MATINEANÄYTÖS" }],
      unmappedLabels: [],
    });
  });

  it("lists a programme of short films as an event", () => {
    expect(listing("VISIONI SARDE 2026")).toMatchObject({ kind: "event", runtimeMinutes: 73 });
    expect(show("visioni-sarde-2026-202611281500")).toMatchObject({
      tags: ["free"],
      subtitles: { kind: "languages", languages: ["en"] },
    });
  });

  it("warns about a row whose weekday fits no date", () => {
    const wrong = HTML.replace("Su 1.11.", "Ma 1.11.");
    const result = parseOulunElokuvakeskus(snapshot({ html: wrong }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
