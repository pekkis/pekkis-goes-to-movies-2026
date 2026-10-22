import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import { parseTribe } from "../../../src/providers/tribe/parse.ts";
import { findSeries } from "../../../src/series/registry.ts";
import type { TribeRawSnapshot } from "../../../src/providers/tribe/raw.ts";
import { TRIBE_SITES } from "../../../src/providers/tribe/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const RITZ = TRIBE_SITES.find((s) => s.provider === "ritzvaasa")!;
const MUHOS = TRIBE_SITES.find((s) => s.provider === "tahtikino")!;
type Page = { events: Record<string, unknown>[]; total_pages: number };
const page = (name: string) => loadFixture("tribe", `${name}-events.json`) as Page;
const snapshot = (pages: unknown[], overrides: Partial<TribeRawSnapshot> = {}) => ({
  fetchedAt: "2026-10-14T09:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  pages,
  ...overrides,
});

describe("parseTribe: Ritz Vaasa", () => {
  const batch = parseTribe(snapshot([page("ritz")]), RITZ);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listingOf = (id: string) => batch.listings.find((l) => l.id === show(id).listingId)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "events-calendar", booking: "door" });
    expect(batch.screenings).toHaveLength(3);
  });

  it("reads the time, the labelled languages and the runtime line", () => {
    expect(show("10003757")).toMatchObject({
      startsAt: "2026-10-18T15:00:00+03:00",
      businessDate: "2026-10-18",
      audio: ["en", "lt"],
      subtitles: { kind: "languages", languages: ["fi", "en"] },
      ticketUrl: "https://ritz.fi/event/svecias-the-visitor/2026-10-18/",
      unmappedLabels: [],
    });
    expect(listingOf("10003757")).toMatchObject({
      title: { fi: "Svečias – The Visitor" },
      runtimeMinutes: 114,
    });
  });

  it('reads "English [Finnish]" titles: the Finnish title in brackets (2026-10-20)', () => {
    const ritz = page("ritz");
    const events = ritz.events.map((e) =>
      e["id"] === 10003757 ? { ...e, title: "Tell Everyone [Kerro kaikille]" } : e,
    );
    const result = parseTribe(snapshot([{ ...ritz, events }]), RITZ);
    const listing = result.listings.find(
      (l) => l.id === result.screenings.find((s) => s.sourceId === "10003757")!.listingId,
    );
    expect(listing?.title).toEqual({ fi: "Kerro kaikille", en: "Tell Everyone" });
    // Square brackets elsewhere, or at a site without the quirk, stay as they are.
    const plain = parseTribe(snapshot([{ ...ritz, events }]), {
      ...RITZ,
      bracketedFinnishTitle: false,
    });
    expect(plain.listings.map((l) => l.title.fi)).toContain("Tell Everyone [Kerro kaikille]");
  });

  it("takes a year and an age limit out of the title", () => {
    expect(listingOf("10003749")).toMatchObject({ title: { fi: "Wholetrain" }, year: 2006 });
    expect(listingOf("10003775")).toMatchObject({
      title: { fi: "Knitting Cinema!" },
      rating: "K-18",
    });
  });

  it("publishes no price for a band of values", () => {
    expect(show("10003749").price).toBeUndefined();
  });

  it("skips, and says so, an event outside the category", () => {
    const edited = page("ritz");
    edited.events[0]!["categories"] = [{ id: 7, slug: "konsertit" }];
    const result = parseTribe(snapshot([edited]), RITZ);
    expect(result.screenings).toHaveLength(2);
    expect(result.warnings.map((w) => w.code)).toEqual(["unclaimed-event"]);
  });

  it("refuses a start whose local and UTC stamps disagree", () => {
    const edited = page("ritz");
    edited.events[0]!["utc_start_date"] = "2026-10-18 11:00:00";
    const result = parseTribe(snapshot([edited]), RITZ);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-start"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("reads every page", () => {
    const [first, ...rest] = page("ritz").events;
    const result = parseTribe(
      snapshot([
        { events: [first], total_pages: 2 },
        { events: rest, total_pages: 2 },
      ]),
      RITZ,
    );
    expect(result.screenings).toHaveLength(3);
  });
});

describe("parseTribe: Tähti Kino, Muhos", () => {
  const batch = parseTribe(snapshot([page("muhos")]), MUHOS);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listingOf = (id: string) => batch.listings.find((l) => l.id === show(id).listingId)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.screenings).toHaveLength(3);
  });

  it("strips the title suffix and reads the single price", () => {
    expect(listingOf("45286")).toMatchObject({ title: { fi: "Pirjo i Sverige" }, rating: "S" });
    expect(show("45286").price).toEqual({ amountCents: 1300, currency: "EUR" });
  });

  it('reads "Ikäraja K-7. …" and "Kesto 2 h 38 min | K-16 | …"', () => {
    expect(listingOf("45266")).toMatchObject({
      title: { fi: "Ryhmä Hau: Dinoelokuva" },
      rating: "K-7",
    });
    expect(listingOf("45343")).toMatchObject({
      title: { fi: "Lapin sota" },
      rating: "K-16",
      runtimeMinutes: 158,
    });
  });

  it('takes a series prefix off the title: "KirjastoKino: One Battle After Another" (2026-10-22)', () => {
    // Trimmed from the live feed; "Kirjastokino" is in the series registry.
    const kirjastokino = {
      id: 45573,
      title: "KirjastoKino: One Battle After Another",
      start_date: "2026-10-28 17:00:00",
      utc_start_date: "2026-10-28 15:00:00",
      all_day: false,
      categories: [{ id: 106, slug: "elokuvat" }],
      cost: "",
      cost_details: { values: [] },
      url: "https://muhos.fi/tapahtuma/kirjastokino-one-battle-after-another/",
      description: "",
    };
    const prefixed = parseTribe(
      snapshot([{ events: [kirjastokino], total_pages: 1 }], { from: "2026-10-22", days: 7 }),
      MUHOS,
    );
    expect(() => ProviderBatch.parse(prefixed)).not.toThrow();
    expect(prefixed.warnings).toEqual([]);
    expect(prefixed.listings[0]).toMatchObject({ title: { fi: "One Battle After Another" } });
    // The parser emits the name as printed; the pull resolves it to the registry's id.
    expect(prefixed.screenings[0]).toMatchObject({
      series: ["KirjastoKino"],
      labels: [{ source: "title.prefix", text: "KirjastoKino" }],
    });
    expect(findSeries("KirjastoKino")).toBe("kirjastokino");
  });
});
