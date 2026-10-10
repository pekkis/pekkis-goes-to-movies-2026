import { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import {
  availabilityOf,
  noteTags,
  parseKinola,
  parseLanguageList,
  parseSubtitleList,
} from "../../../src/providers/kinola/parse.ts";
import type { KinolaRawSnapshot } from "../../../src/providers/kinola/raw.ts";
import { KINOLA_SITES, type KinolaSite } from "../../../src/providers/kinola/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const site = (tenant: string): KinolaSite => {
  const found = KINOLA_SITES.find((s) => s.tenant === tenant);
  if (!found) throw new Error(`No site ${tenant}`);
  return found;
};

const snapshot = (
  tenant: string,
  overrides: Partial<KinolaRawSnapshot> = {},
): KinolaRawSnapshot => ({
  fetchedAt: "2026-10-10T07:00:00.000Z",
  from: "2026-10-10",
  days: 120,
  pages: [loadFixture("kinola", `${tenant}-events.json`)],
  ...overrides,
});

const parse = (tenant: string, overrides: Partial<KinolaRawSnapshot> = {}) =>
  parseKinola(snapshot(tenant, overrides), site(tenant));

const show = (batch: ProviderBatch, idPrefix: string) => {
  const found = batch.screenings.find((s) => s.sourceId.startsWith(idPrefix));
  if (!found) throw new Error(`No screening ${idPrefix}`);
  return found;
};

describe("field parsers", () => {
  it("reads Finnish, English and odd language names", () => {
    expect(parseLanguageList(["englanti", "ruotsi ", "Polish", "kiillottaa"])).toEqual({
      langs: ["en", "sv", "pl"],
      dubbed: false,
      unknown: [],
    });
    expect(parseLanguageList(["Dubattu englanniksi"])).toEqual({
      langs: ["en"],
      dubbed: true,
      unknown: [],
    });
    expect(parseLanguageList(["Taiwan", ""])).toEqual({
      langs: [],
      dubbed: false,
      unknown: ["Taiwan"],
    });
  });

  it("reads subtitles, the misspelt 'no subtitles' included", () => {
    expect(parseSubtitleList(["suomi", "ruotsi "]).subtitles).toEqual({
      kind: "languages",
      languages: ["fi", "sv"],
    });
    expect(parseSubtitleList(["Ei teksitystä"]).subtitles).toEqual({ kind: "none" });
    expect(parseSubtitleList(["Ei tekstitystä"]).subtitles).toEqual({ kind: "none" });
    expect(parseSubtitleList([]).subtitles).toEqual({ kind: "unknown" });
  });

  it("maps free seats and visibility to availability", () => {
    expect(availabilityOf({ freeSeats: 0, visibility: "public" })).toBe("sold-out");
    expect(availabilityOf({ freeSeats: 12, visibility: "public" })).toBe("available");
    expect(availabilityOf({ freeSeats: 68, visibility: "coming_soon" })).toBe("not-bookable");
    expect(availabilityOf({ freeSeats: null, visibility: "public" })).toBe("unknown");
  });

  it("reads only notes that start with a label", () => {
    expect(noteTags("Ensi-ilta")).toEqual(["premiere"]);
    expect(noteTags("Premiere.\r\nSerial tickets are not valid.")).toEqual(["premiere"]);
    expect(noteTags("Ennakkonäytös. Ensi-ilta 30.10.")).toEqual(["preview"]);
    expect(noteTags("Espanjalaisen elokuvan viikko. Vapaa pääsy!")).toEqual([]);
    expect(noteTags(null)).toEqual([]);
  });
});

describe("parseKinola", () => {
  it.each(["myyri", "orion", "kilta", "laika", "sheryl"])(
    "%s: a valid batch without warnings",
    (tenant) => {
      const batch = parse(tenant);
      expect(() => ProviderBatch.parse(batch)).not.toThrow();
      expect(batch.warnings).toEqual([]);
      expect(batch.screenings.length).toBeGreaterThan(0);
      expect(batch.provider).toMatchObject({
        id: site(tenant).provider,
        platform: "kinola",
        booking: "buy",
      });
    },
  );

  it("maps a Kino Myyri screening, copying the checkout link", () => {
    const batch = parse("myyri");
    expect(show(batch, "72d15db4")).toMatchObject({
      id: "kinomyyri:show:72d15db4-d54e-4436-aa3d-8a608c827a35",
      venueId: "kinomyyri:venue:myyrmaki",
      startsAt: "2026-10-10T14:00:00+03:00",
      businessDate: "2026-10-10",
      audio: ["es"],
      subtitles: { kind: "languages", languages: ["en"] },
      // "Espanjalaisen elokuvan viikko: …" is a series; the show is free.
      series: ["Espanjalaisen elokuvan viikko"],
      price: { amountCents: 0, currency: "EUR" },
      availability: "available",
      ticketUrl: "https://www.myyrikino.fi/checkout/72d15db4-d54e-4436-aa3d-8a608c827a35",
    });
    expect(batch.listings.find((l) => l.sourceId.startsWith("9f685f7e"))).toMatchObject({
      title: { fi: "Campeones – Mestarit" },
      originalTitle: "Campeones",
      year: 2018,
      runtimeMinutes: 124,
      rating: "K-12",
      kind: "film",
    });
    // One venue, one room of the same name: no separate auditorium.
    expect(batch.auditoriums).toEqual([]);
  });

  it("passes IMDb ids and original titles to matching", () => {
    const orion = parse("orion");
    expect(orion.listings.find((l) => l.title.fi === "Talvitarina")).toMatchObject({
      originalTitle: "Conte d'hiver",
      imdbId: "tt0104008",
      year: 1992,
    });
    const kilta = parse("kilta");
    expect(kilta.listings.every((l) => l.imdbId?.startsWith("tt"))).toBe(true);
  });

  it("notes a price range and keeps the lowest price", () => {
    expect(show(parse("orion"), "b243f151").price).toEqual({
      amountCents: 1000,
      currency: "EUR",
      note: "10 €–12,50 €",
    });
  });

  it("reads Kilta: licensed shows, no checkout link, shows not yet on sale", () => {
    const batch = parse("kilta");
    expect(show(batch, "39be45bb")).toMatchObject({
      licensed: true,
      ticketUrl: "https://www.kinokilta.fi/naytokset/",
    });
    expect(show(batch, "40959653")).toMatchObject({
      availability: "not-bookable",
      series: ["Kinokopla"],
    });
    expect(show(batch, "0ef2a0a9")).toMatchObject({ audio: ["en"], dubbed: true });
    expect(show(batch, "5dab2762").subtitles).toEqual({ kind: "none" });
    expect(show(batch, "7fee742f").unmappedLabels).toEqual(["language:Taiwan"]);
  });

  it("tells Kino Laika's live acts from films", () => {
    const batch = parse("laika");
    expect(batch.listings.find((l) => l.title.fi === "Arppa")?.kind).toBe("event");
    expect(batch.listings.find((l) => l.title.fi === "AKI")?.kind).toBe("film");
    expect(show(batch, "77149743").availability).toBe("sold-out");
  });

  it("does not apply Laika's rule where it was not checked", () => {
    // Without the site rule, the same bare production stays a film.
    const laika = loadFixture("kinola", "laika-events.json") as { data: unknown[] };
    const batch = parseKinola(snapshot("laika", { pages: [laika] }), {
      ...site("laika"),
      bareProductionsAreEvents: false,
    });
    expect(batch.listings.find((l) => l.title.fi === "Arppa")?.kind).toBe("film");
  });

  it("names Cinema Sheryl's venue by the API's building name, in Espoo", () => {
    const batch = parse("sheryl");
    expect(batch.venues).toEqual([
      expect.objectContaining({ name: "Cinema Sheryl", city: "Espoo" }),
    ]);
    expect(show(batch, "0647889f").audio).toEqual(["zh", "en"]);
  });

  it("keeps only the requested window", () => {
    const batch = parse("kilta", { days: 7 });
    expect(batch.window).toEqual({ from: "2026-10-10", to: "2026-10-16" });
    expect(batch.screenings.map((s) => s.businessDate)).toEqual(["2026-10-10", "2026-10-11"]);
    expect(new Set(batch.screenings.map((s) => s.listingId)).size).toBe(batch.listings.length);
  });

  it("warns about venues not in the config, and broken events", () => {
    const page = loadFixture("kinola", "sheryl-events.json") as { data: Record<string, unknown>[] };
    const moved = { ...page, data: [{ ...page.data[0]!, venue: { name: "Väre" } }, { id: "x" }] };
    const batch = parseKinola(snapshot("sheryl", { pages: [moved] }), site("sheryl"));
    expect(batch.warnings.map((w) => w.code).sort()).toEqual(["invalid-event", "unclaimed-venue"]);
    expect(batch.screenings).toEqual([]);
  });
});
