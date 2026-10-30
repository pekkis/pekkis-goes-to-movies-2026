import { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import { isPublicScreening, parseJohku } from "../../../src/providers/johku/parse.ts";
import type { JohkuRawSnapshot } from "../../../src/providers/johku/raw.ts";
import { JOHKU_SITES, type JohkuSite } from "../../../src/providers/johku/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const site = (shop: string): JohkuSite => {
  const found = JOHKU_SITES.find((s) => s.shop === shop);
  if (!found) {
    throw new Error(`No site ${shop}`);
  }
  return found;
};

const snapshot = (
  shop: string,
  categories: number[],
  overrides: Partial<JohkuRawSnapshot> = {},
): JohkuRawSnapshot => ({
  fetchedAt: "2026-10-12T07:00:00.000Z",
  from: "2026-10-12",
  days: 30,
  schedules: Object.fromEntries(
    categories.map((c) => [String(c), loadFixture("johku", `${shop}-c${c}.json`)]),
  ),
  ...overrides,
});

const parse = (shop: string, categories: number[], overrides: Partial<JohkuRawSnapshot> = {}) =>
  parseJohku(snapshot(shop, categories, overrides), site(shop));

const show = (batch: ProviderBatch, sourceId: string) => {
  const found = batch.screenings.find((s) => s.sourceId === sourceId);
  if (!found) {
    throw new Error(`No screening ${sourceId}`);
  }
  return found;
};

describe("field parsers", () => {
  it("tells screenings from hall hire, closures and private bookings", () => {
    expect(isPublicScreening({ price: "13", agelimit: "S", maccsboxlanguage: "FI" })).toBe(true);
    // A free screening still has film data.
    expect(isPublicScreening({ price: null, agelimit: "K-7", maccsboxlanguage: "-" })).toBe(true);
    expect(isPublicScreening({ price: null, agelimit: null, maccsboxlanguage: "-" })).toBe(false);
  });
});

describe("parseJohku", () => {
  it.each([
    ["kinokulma", [1]],
    ["biomarilyn", [1, 9]],
    ["vihdinkino", [9]],
    ["bioforum", [9]],
    ["kulttuurimylly", [2]],
  ])("%s: a valid batch without warnings", (shop, categories) => {
    const batch = parse(shop, categories);
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.screenings.length).toBeGreaterThan(0);
    expect(batch.provider).toMatchObject({
      id: site(shop).provider,
      platform: "johku",
      booking: "buy",
    });
  });

  it("maps a Kinokulma screening and leaves out hall hire, closures and private bookings", () => {
    const batch = parse("kinokulma", [1]);
    expect(batch.listings.map((l) => l.title.fi).toSorted()).toEqual(["Digger", "Pirjo i Sverige"]);
    expect(show(batch, "6457")).toMatchObject({
      id: "kinokulma:show:6457",
      venueId: "kinokulma:venue:oulainen",
      listingId: "kinokulma:film:1120",
      startsAt: "2026-10-14T19:00:00+03:00",
      audio: ["fi"],
      subtitles: { kind: "languages", languages: ["fi"] },
      availability: "available",
      price: { amountCents: 1300, currency: "EUR", note: "other ticket types available" },
      ticketUrl: "https://kinokulma.fi/fi_FI/pirjo-i-sverige",
    });
    expect(batch.listings.find((l) => l.sourceId === "1120")).toMatchObject({
      runtimeMinutes: 88,
      rating: "S",
      kind: "film",
    });
    // The hall is named after the venue's own resource: one auditorium.
    expect(batch.auditoriums).toEqual([expect.objectContaining({ name: "Kulmasali", seats: 113 })]);
  });

  it("reads a shared category with several venues, one of them with two halls", () => {
    const batch = parse("elokuviin", [2]);
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.venues.map((v) => v.id)).toEqual([
      "sunkino:venue:kauhava",
      "sunkino:venue:alavus",
      "sunkino:venue:ahtari",
      "sunkino:venue:alajarvi",
    ]);
    // Kino Kyntäjä's two halls are one venue with two auditoriums.
    expect(show(batch, "3965").venueId).toBe("sunkino:venue:alavus");
    expect(show(batch, "3966").venueId).toBe("sunkino:venue:alavus");
    expect(
      batch.auditoriums.filter((a) => a.venueId === "sunkino:venue:alavus").map((a) => a.name),
    ).toEqual(["Kino Kyntäjä, sali 1 (ALAVUS)", "Kino Kyntäjä, sali 2 (ALAVUS)"]);
  });

  it("leaves out a private screening in the programme (Sun Kino, 2026-10-30)", () => {
    const payload = loadFixture("johku", "elokuviin-c2.json") as { data: { text: string }[] };
    const data = payload.data.map((e, i) =>
      i === 0 ? { ...e, text: `YKSITYISNÄYTÖS! ${e.text}` } : e,
    );
    const batch = parse("elokuviin", [2], { schedules: { "2": { data } } });
    expect(batch.warnings).toEqual([]);
    expect(batch.screenings.map((s) => s.sourceId)).not.toContain("3965");
    expect(batch.screenings).toHaveLength(4);
  });

  it("skips coming-soon entries and publishes a show in two blocks once", () => {
    const batch = parse("biomarilyn", [1, 9]);
    expect(batch.screenings.map((s) => s.sourceId).toSorted()).toEqual(["10158", "10161"]);
    expect(batch.listings.find((l) => l.title.fi === "Unohdettu Saari")?.originalTitle).toBe(
      "Forgotten Island",
    );
  });

  it("marks a full hall sold out and reads a charity screening's labels", () => {
    const batch = parse("vihdinkino", [9]);
    expect(show(batch, "6713")).toMatchObject({
      availability: "sold-out",
      price: { amountCents: 200 },
      series: ["MLL-näytös"],
      tags: ["kids"],
    });
    expect(batch.listings.find((l) => l.sourceId === "1107")?.originalTitle).toBe("Toy Story 5");
  });

  it("reads Bio Forum's leading version marker", () => {
    const batch = parse("bioforum", [9]);
    expect(batch.listings[0]?.title).toEqual({ fi: "Bortglömda ön" });
    expect(batch.screenings[0]).toMatchObject({ audio: ["sv"], dubbed: true });
  });

  it("tags family and senior screenings from their title labels", () => {
    const batch = parse("kulttuurimylly", [2]);
    expect(show(batch, "1081")).toMatchObject({ tags: ["kids"] });
    expect(show(batch, "1074")).toMatchObject({ tags: ["senior"] });
    expect(batch.listings.map((l) => l.title.fi).toSorted()).toEqual([
      "Presidentin Kyyditys",
      "Unohdettu Saari",
    ]);
  });

  it("warns about halls no venue claims (Kulttuurimylly's theatre)", () => {
    const batch = parseJohku(snapshot("kulttuurimylly", [5]), site("kulttuurimylly"));
    expect(batch.screenings).toEqual([]);
    expect(batch.warnings).toEqual([
      expect.objectContaining({
        code: "unclaimed-hall",
        context: expect.objectContaining({ hall: "Feeniks-sali (Teatteri)" }),
      }),
    ]);
  });

  it("keeps only the requested window", () => {
    const batch = parse("kinokulma", [1], { days: 3 });
    expect(batch.window).toEqual({ from: "2026-10-12", to: "2026-10-14" });
    expect(batch.screenings.map((s) => s.sourceId)).toEqual(["6457"]);
  });

  it("turns a broken response and entry into warnings", () => {
    const batch = parseJohku(
      snapshot("kinokulma", [1], { schedules: { "1": { data: [{ id: "1" }] }, "2": "<html>" } }),
      site("kinokulma"),
    );
    expect(batch.warnings.map((w) => w.code).toSorted()).toEqual([
      "invalid-entry",
      "invalid-response",
    ]);
  });
});
