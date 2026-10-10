import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import {
  availabilityOf,
  extractFilmPage,
  filmLinks,
  isEmptyProgramme,
  parseDuration,
  parseEtiketti,
  parseLanguages,
  parseSubtitles,
  resolvePlace,
  roomName,
} from "../../../src/providers/etiketti/parse.ts";
import type { EtikettiRawSnapshot } from "../../../src/providers/etiketti/raw.ts";
import { ETIKETTI_SITES, type EtikettiSite } from "../../../src/providers/etiketti/sites.ts";

const html = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/etiketti", `${name}.html`), "utf8");

const site = (provider: string): EtikettiSite => {
  const found = ETIKETTI_SITES.find((s) => s.provider === provider);
  if (!found) throw new Error(`No site ${provider}`);
  return found;
};

const snapshot = (
  films: Record<string, string>,
  overrides: Partial<EtikettiRawSnapshot> = {},
): EtikettiRawSnapshot => ({
  fetchedAt: "2026-10-10T07:00:00.000Z",
  from: "2026-10-10",
  days: 30,
  listing: "",
  films,
  ...overrides,
});

const parse = (provider: string, fixture: string, overrides: Partial<EtikettiRawSnapshot> = {}) =>
  parseEtiketti(snapshot({ "/elokuvat/3298/digger": html(fixture) }, overrides), site(provider));

describe("listing", () => {
  it("collects film page links, deduplicated by id", () => {
    const links = filmLinks(html("kotka-listing"));
    expect(links).toHaveLength(17);
    expect(links).toContain("/elokuvat/3298/digger");
    expect(new Set(links).size).toBe(links.length);
    expect(
      filmLinks(
        '<a href="/elokuvat/1/a">x</a><a href="/elokuvat/1/a">y</a><a href="/ikarajat">z</a>',
      ),
    ).toEqual(["/elokuvat/1/a"]);
  });

  it("tells an empty programme from an unreadable page", () => {
    expect(
      isEmptyProgramme('<div class="movie-list"><p>Ei ohjelmistoa saatavilla.</p></div>'),
    ).toBe(true);
    expect(isEmptyProgramme("<html><body>Something else</body></html>")).toBe(false);
  });
});

describe("field parsers", () => {
  it("reads durations", () => {
    expect(parseDuration("2 h 9 min")).toBe(129);
    expect(parseDuration("95 min")).toBe(95);
    expect(parseDuration("2 h")).toBe(120);
    expect(parseDuration("pitkä")).toBeUndefined();
  });

  it("reads Finnish language names, also several", () => {
    expect(parseLanguages("Suomi ja ruotsi")).toEqual(["fi", "sv"]);
    expect(parseLanguages("englanti")).toEqual(["en"]);
    expect(parseLanguages("heprea")).toEqual(["he"]);
    expect(parseLanguages("klingon")).toBeUndefined();
  });

  it("reads subtitles; 'Ei tekstitystä' is none unless the site prints it unreliably", () => {
    expect(parseSubtitles("Suomi ja ruotsi", false).subtitles).toEqual({
      kind: "languages",
      languages: ["fi", "sv"],
    });
    expect(parseSubtitles("Ei tekstitystä", false).subtitles).toEqual({ kind: "none" });
    expect(parseSubtitles("Ei tekstitystä", true).subtitles).toEqual({ kind: "unknown" });
    expect(parseSubtitles(undefined, false).subtitles).toEqual({ kind: "unknown" });
    expect(parseSubtitles("klingon", false)).toEqual({
      subtitles: { kind: "unknown" },
      unknown: "klingon",
    });
  });

  it("maps free seats to availability", () => {
    expect(availabilityOf(0, 100)).toBe("sold-out");
    expect(availabilityOf(9, 100)).toBe("few-left");
    expect(availabilityOf(10, 100)).toBe("available");
    expect(availabilityOf(undefined, undefined)).toBe("unknown");
  });

  it("tidies all-caps room names, keeping acronyms", () => {
    expect(roomName("SALI 3")).toBe("Sali 3");
    expect(roomName("VIP-SALI")).toBe("VIP-sali");
    expect(roomName("DIGI 1")).toBe("Digi 1");
    expect(roomName("Kino Aurora")).toBe("Kino Aurora");
  });
});

describe("resolvePlace", () => {
  const savon = site("savonkinot").venues;

  it("finds the venue part and the room after it", () => {
    expect(resolvePlace(savon, "JOENSUU | TAPIO | TAPIO 3")).toMatchObject({
      venue: { slug: "tapio" },
      room: "TAPIO 3",
    });
    expect(resolvePlace(site("elokuvateatteristar").venues, "STAR | SALI 4")).toMatchObject({
      venue: { slug: "oulu" },
      room: "SALI 4",
    });
  });

  it("drops a room that repeats the venue, and venues with no room", () => {
    expect(resolvePlace(savon, "IISALMI | KUVALIPAS | KUVALIPAS")).toEqual({
      venue: expect.objectContaining({ slug: "kuvalipas" }),
    });
    expect(resolvePlace(site("cine").venues, "KERAVA | CINE KEUDA-TALO")).toEqual({
      venue: expect.objectContaining({ slug: "keuda-talo" }),
    });
  });

  it("tells two places of one site apart", () => {
    const juha = site("kinojuha").venues;
    expect(resolvePlace(juha, "KINO JUHA")?.venue.slug).toBe("kino-juha");
    expect(resolvePlace(juha, "VIP-SALI")?.venue.slug).toBe("vip-sali");
  });

  it("gives rows without a place line to the venue without a place, if exactly one", () => {
    expect(resolvePlace(site("cinemaniagara").venues, undefined)?.venue.slug).toBe("tampere");
    expect(resolvePlace(savon, undefined)).toBeUndefined();
    expect(resolvePlace(savon, "OULU | NOWHERE")).toBeUndefined();
  });
});

describe("extractFilmPage", () => {
  it("reads labelled facts, genres and the age icon", () => {
    const { film } = extractFilmPage(html("savonkinot-digger"), "/elokuvat/143/digger");
    expect(film).toMatchObject({
      sourceId: "143",
      title: "DIGGER",
      age: "12",
      genres: ["Draama", "Komedia"],
      facts: { Kesto: "2 h 9 min", Kieli: "englanti", Tekstitys: "Suomi ja ruotsi" },
    });
  });

  it("reads Niagara's colonless labels and its production year", () => {
    const { film } = extractFilmPage(html("niagara-autofiktio"), "/elokuvat/71/autofiktio");
    expect(film).toMatchObject({
      facts: { Kieli: "espanja", Kesto: "1 h 52 min", Valmistumisvuosi: "2026" },
      genres: ["Draama", "Fantasia"],
    });
  });
});

describe("parseEtiketti", () => {
  it.each([
    ["kotkanleffat", "kotka-digger"],
    ["savonkinot", "savonkinot-digger"],
    ["kinojuha", "kinojuha-digger"],
    ["cinemaniagara", "niagara-autofiktio"],
    ["kinopirtti", "kinopirtti-digger"],
    ["elokuvateatteristar", "star-digger"],
  ])("%s: produces a valid batch without warnings", (provider, fixture) => {
    const batch = parse(provider, fixture);
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.screenings.length).toBeGreaterThan(0);
    expect(batch.provider).toMatchObject({ id: provider, platform: "etiketti", booking: "buy" });
  });

  it("maps a Kotka-template screening, copying the ticket link", () => {
    const batch = parse("kotkanleffat", "kotka-digger");
    expect(batch.screenings[0]).toMatchObject({
      id: "kotkanleffat:show:56589",
      venueId: "kotkanleffat:venue:trio-123",
      listingId: "kotkanleffat:film:3298",
      startsAt: "2026-10-10T20:00:00+03:00",
      businessDate: "2026-10-10",
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      availability: "available",
      price: { amountCents: 1800, currency: "EUR" },
      ticketUrl: "https://kotkanleffat.fi/salikartta?id=56589",
    });
    // "Kieli: Alkuperäinen" says nothing about the language.
    expect(batch.screenings[0]!.audio).toEqual([]);
    expect(batch.auditoriums.map((a) => a.name)).toEqual(["VIP-sali"]);
    expect(batch.listings[0]).toMatchObject({
      title: { fi: "DIGGER" },
      runtimeMinutes: 129,
      rating: "K-12",
    });
  });

  it("maps tags: known ones to tags, the bar icon to licensed", () => {
    const kotka = parse("kotkanleffat", "kotka-digger");
    expect(kotka.screenings.find((s) => s.sourceId === "56644")?.tags).toEqual(["discount"]);
    const pirtti = parse("kinopirtti", "kinopirtti-digger");
    expect(pirtti.screenings.find((s) => s.sourceId === "53993")?.licensed).toBe(true);
    expect(pirtti.screenings.find((s) => s.sourceId === "54005")?.licensed).toBeUndefined();
    const niagara = parse("cinemaniagara", "niagara-autofiktio");
    expect(niagara.screenings[0]?.tags).toEqual(["last-screening"]);
  });

  it("splits Savon Kinot's cinemas by place line and drops repeated rooms", () => {
    const batch = parse("savonkinot", "savonkinot-digger");
    const venues = new Set(batch.screenings.map((s) => s.venueId.split(":")[2]));
    expect(venues).toEqual(new Set(["tapio", "maxim", "kuvalipas", "kuvalinna"]));
    expect(batch.screenings.find((s) => s.sourceId === "55678")?.auditoriumId).toBeUndefined();
    expect(batch.screenings[0]!.audio).toEqual(["en"]);
  });

  it("reads Niagara's template: time, price, seats, year", () => {
    const batch = parse("cinemaniagara", "niagara-autofiktio");
    expect(batch.screenings[0]).toMatchObject({
      startsAt: "2026-10-14T20:30:00+03:00",
      audio: ["es"],
      price: { amountCents: 1300 },
      availability: "available",
    });
    expect(batch.listings[0]?.year).toBe(2026);
  });

  it("deduplicates rows printed twice (Niagara's desktop and mobile copies)", () => {
    const page = html("niagara-autofiktio");
    const doubled = page.replace(/(<div class="item [\s\S]*?<\/div>\s*<\/div>\s*<\/div>)/, "$1$1");
    expect(doubled.length).toBeGreaterThan(page.length);
    const batch = parseEtiketti(
      snapshot({ "/elokuvat/71/autofiktio": doubled }),
      site("cinemaniagara"),
    );
    expect(batch.screenings).toHaveLength(1);
  });

  it("warns about places no venue claims, once per place", () => {
    const savon = site("savonkinot");
    const withoutTapio = { ...savon, venues: savon.venues.filter((v) => v.slug !== "tapio") };
    const batch = parseEtiketti(
      snapshot({ "/elokuvat/143/digger": html("savonkinot-digger") }),
      withoutTapio,
    );
    expect(batch.warnings).toEqual([
      expect.objectContaining({
        code: "unclaimed-place",
        context: { place: "JOENSUU | TAPIO | TAPIO 3", shows: 3 },
      }),
    ]);
    expect(batch.screenings.some((s) => s.venueId.endsWith(":tapio"))).toBe(false);
  });

  it("keeps only screenings inside the requested window", () => {
    const batch = parse("elokuvateatteristar", "star-digger", { days: 2 });
    expect(batch.window).toEqual({ from: "2026-10-10", to: "2026-10-11" });
    expect(batch.screenings.map((s) => s.businessDate)).toEqual(["2026-10-10", "2026-10-11"]);
  });

  it("strips version markers and title prefixes into data", () => {
    const page = html("kotka-digger").replace(
      "<h1>DIGGER</h1>",
      "<h1>Ennakkonäytös: Digger (DUB)</h1>",
    );
    const batch = parseEtiketti(snapshot({ "/elokuvat/3298/digger": page }), site("kotkanleffat"));
    expect(batch.listings[0]?.title).toEqual({ fi: "Digger" });
    expect(batch.screenings[0]).toMatchObject({ tags: ["preview"], audio: ["fi"], dubbed: true });
  });

  it("turns a broken film page into a warning", () => {
    const batch = parseEtiketti(
      snapshot({ "/elokuvat/1/x": "<html><body>nope</body></html>" }),
      site("kotkanleffat"),
    );
    expect(batch.warnings.map((w) => w.code)).toEqual(["invalid-film"]);
    expect(batch.screenings).toEqual([]);
  });
});
