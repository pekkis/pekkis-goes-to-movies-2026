import { describe, expect, it } from "vitest";
import { ProviderBatch } from "../../../src/model/schema.ts";
import {
  parseFinnkino,
  parseLanguageAttribute,
  parseRating,
} from "../../../src/providers/finnkino/parse.ts";
import type { FinnkinoRawSnapshot } from "../../../src/providers/finnkino/raw.ts";
import { loadFixture } from "../../fixtures.ts";

const snapshot = (overrides: Partial<FinnkinoRawSnapshot> = {}): FinnkinoRawSnapshot => ({
  ...(loadFixture("finnkino", "snapshot.json") as FinnkinoRawSnapshot),
  ...overrides,
});

const show = (batch: ProviderBatch, sourceId: string) => {
  const found = batch.screenings.find((s) => s.sourceId === sourceId);
  if (!found) throw new Error(`No screening ${sourceId}`);
  return found;
};

describe("parseFinnkino", () => {
  const batch = parseFinnkino(snapshot());

  it("produces a valid batch without warnings or unmapped labels", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.screenings.flatMap((s) => s.unmappedLabels)).toEqual([]);
  });

  it("maps a venue from the site's address", () => {
    expect(batch.venues.find((v) => v.sourceId === "1004")).toEqual({
      id: "finnkino:venue:1004",
      provider: "finnkino",
      sourceId: "1004",
      name: "Promenadi Pori",
      city: "Pori",
      address: "Yrjönkatu 17",
      postalCode: "28100",
      geo: { lat: 61.51614827, lon: 21.77650159 },
    });
  });

  it("parses an original-language show with Finnish and Swedish subtitles", () => {
    expect(show(batch, "1004-5833")).toMatchObject({
      id: "finnkino:show:1004-5833",
      venueId: "finnkino:venue:1004",
      listingId: expect.stringMatching(/^finnkino:film:HO/),
      audio: ["en"],
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      presentation: { projection: "digital", dimension: "2d", formats: [] },
      availability: "available",
      ticketUrl: "https://www.finnkino.fi/liput/valitse-paikat/?showtimeId=1004-5833",
    });
  });

  it("reads Finnish audio without subtitle attributes as no subtitles", () => {
    expect(show(batch, "1095-7848")).toMatchObject({ audio: ["fi"], subtitles: { kind: "none" } });
  });

  it("turns open captions into Finnish subtitles and an accessibility tag", () => {
    expect(show(batch, "1111-26299")).toMatchObject({
      audio: ["fi"],
      subtitles: { kind: "languages", languages: ["fi"] },
      tags: ["accessible"],
    });
  });

  it("splits compound language codes", () => {
    expect(show(batch, "1100-15225").audio).toEqual(["ko", "ja"]);
    expect(show(batch, "1100-15240").audio).toEqual(["fi", "sv"]);
    expect(show(batch, "1100-15391").audio).toEqual(["tr"]);
  });

  it("leaves audio unknown for 'several languages' and for shows without language data", () => {
    expect(show(batch, "1100-15212").audio).toEqual([]);
    expect(show(batch, "1095-7932")).toMatchObject({ audio: [], subtitles: { kind: "unknown" } });
  });

  it("maps alcohol service and the K-18 limit", () => {
    expect(show(batch, "1004-5830")).toMatchObject({ licensed: true, ageLimit: "K-18" });
    const licensed = show(batch, "1100-15222");
    expect(licensed.licensed).toBe(true);
    expect(licensed).not.toHaveProperty("ageLimit");
    expect(show(batch, "1095-7848")).not.toHaveProperty("licensed");
  });

  it("maps premium formats and tags", () => {
    expect(show(batch, "1107-10403").presentation.formats).toEqual(["luxe"]);
    expect(show(batch, "1101-12732").presentation.formats).toEqual(["isense"]);
    expect(show(batch, "1162-12065").presentation.formats).toEqual(["imax"]);
    expect(show(batch, "1095-7931").tags).toEqual(["preview"]);
    expect(show(batch, "1095-7042").tags).toEqual(["event-cinema"]);
  });

  it("marks event cinema listings", () => {
    const listing = batch.listings.find((l) => l.id === show(batch, "1095-7042").listingId);
    expect(listing).toMatchObject({ title: { fi: "Queen Budapest" }, kind: "event" });
    expect(batch.listings.find((l) => l.title.fi === "Tony")?.kind).toBe("film");
  });

  it("maps the rating and leaves countries empty", () => {
    const tony = batch.listings.find((l) => l.title.fi === "Tony");
    expect(tony).toMatchObject({ rating: "K-16", runtimeMinutes: 109, countries: [] });
  });

  it("is not bookable before the advance booking rule opens sales", () => {
    const raw = snapshot();
    const response = raw.showtimes["fixture"] as {
      relatedData: {
        filmAdvanceBookingRules: {
          filmId: string;
          siteId: string;
          bookingPeriods: { startsAt: string }[];
        }[];
      };
      showtimes: { id: string; filmId: string; siteId: string }[];
    };
    const target = response.showtimes.find((s) => s.id === "1004-5821")!;
    const rule = response.relatedData.filmAdvanceBookingRules.find(
      (r) => r.filmId === target.filmId && r.siteId === target.siteId,
    )!;
    const before = new Date(Date.parse(rule.bookingPeriods[0]!.startsAt) - 60_000).toISOString();

    const early = show(parseFinnkino({ ...raw, fetchedAt: before }), "1004-5821");
    expect(early.availability).toBe("not-bookable");
    expect(early).not.toHaveProperty("ticketUrl");
    expect(show(batch, "1004-5821").availability).toBe("available");
  });

  it("turns broken data into warnings", () => {
    const raw = snapshot();
    const response = raw.showtimes["fixture"] as { showtimes: unknown[] };
    response.showtimes.push({ id: "broken" });
    const result = parseFinnkino({ ...raw, showtimes: { ...raw.showtimes, bad: { nope: 1 } } });
    expect(result.warnings.map((w) => w.code).sort()).toEqual([
      "invalid-showtime",
      "invalid-showtimes",
    ]);
    expect(result.screenings).toHaveLength(batch.screenings.length);
  });

  it("reports an attribute it does not know", () => {
    const raw = snapshot();
    const response = raw.showtimes["fixture"] as {
      showtimes: { id: string; attributeIds: string[] }[];
      relatedData: { attributes: unknown[] };
    };
    response.relatedData.attributes.push({
      id: "X1",
      name: { text: "Hologram" },
      shortName: { text: "HOLO" },
    });
    response.showtimes.find((s) => s.id === "1004-5833")!.attributeIds.push("X1", "X2");
    expect(show(parseFinnkino(raw), "1004-5833").unmappedLabels).toEqual(["HOLO", "attribute:X2"]);
  });
});

describe("field parsers", () => {
  it.each([
    ["FI-A", { role: "audio", languages: ["fi"] }],
    ["SE-S", { role: "subtitles", languages: ["sv"] }],
    ["KO-JA-A", { role: "audio", languages: ["ko", "ja"] }],
    ["TU-A", { role: "audio", languages: ["tr"] }],
    ["SEVERAL", undefined],
    ["Annisk_K18", undefined],
  ])("parseLanguageAttribute(%s)", (input, expected) => {
    expect(parseLanguageAttribute(input)).toEqual(expected);
  });

  it.each([
    ["S", "S"],
    ["7 A", "K-7"],
    ["12 VA", "K-12"],
    ["16 P", "K-16"],
    ["18 S", "K-18"],
    ["Tulossa", undefined],
    [undefined, undefined],
  ])("parseRating(%s) = %s", (input, expected) => {
    expect(parseRating(input)).toBe(expected);
  });
});
