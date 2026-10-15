import { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import { parseLinkedEvents, withoutCredits } from "../../../src/providers/linkedevents/parse.ts";
import type { LinkedEventsRawSnapshot } from "../../../src/providers/linkedevents/raw.ts";
import { LINKED_EVENTS_SITES } from "../../../src/providers/linkedevents/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const SITE = LINKED_EVENTS_SITES[0]!;
type Page = { meta: { next: string | null }; data: Record<string, unknown>[] };
const page = () => loadFixture("linkedevents", "malmitalo-events.json") as Page;
const snapshot = (overrides: Partial<LinkedEventsRawSnapshot> = {}): LinkedEventsRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  pages: [page()],
  ...overrides,
});

describe("parseLinkedEvents: Kino Helios", () => {
  const batch = parseLinkedEvents(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listingOf = (id: string) => batch.listings.find((l) => l.id === show(id).listingId)!;

  it("produces a valid batch of the cinema's screenings only", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "linked-events", booking: "buy" });
    // The youth film course and the library's writing group are not screenings.
    expect(batch.screenings.map((s) => s.sourceId).toSorted()).toEqual([
      "kulke:68843",
      "kulke:68847",
      "kulke:68857",
      "kulke:69500",
      "kulke:69509",
    ]);
  });

  it("reads the UTC start, the price and the ticket link", () => {
    expect(show("kulke:68847")).toMatchObject({
      startsAt: "2026-10-17T18:00:00+03:00",
      businessDate: "2026-10-17",
      price: { amountCents: 900, currency: "EUR" },
      ticketUrl:
        "https://www.lippu.fi/event/kino-helios-esittaa-kino-helios-tony-malmitalo-22211013/",
    });
  });

  it("takes the cinema's name and the age limit off the title", () => {
    expect(listingOf("kulke:68847")).toMatchObject({ title: { fi: "Tony" }, rating: "K-16" });
    expect(listingOf("kulke:68843")).toMatchObject({
      title: { fi: "Presidentin kyyditys" },
      rating: "K-12",
    });
  });

  it("reads the house's strands", () => {
    expect(show("kulke:69509")).toMatchObject({ series: ["HopeaCine"], tags: ["senior"] });
    expect(listingOf("kulke:69509").title.fi).toBe("Presidentin kyyditys");
    expect(show("kulke:69500").series).toEqual(["Yleisön suosikit"]);
    expect(listingOf("kulke:69500").title.fi).toBe("Teräsleidit – kuin viimeistä päivää");
  });

  it("skips cancelled and postponed events", () => {
    const edited = page();
    edited.data[0]!["event_status"] = "EventCancelled";
    edited.data[1]!["event_status"] = "EventPostponed";
    const result = parseLinkedEvents(snapshot({ pages: [edited] }), SITE);
    expect(result.screenings.map((s) => s.sourceId)).not.toContain("kulke:68847");
    expect(result.screenings.map((s) => s.sourceId)).not.toContain("kulke:68843");
    expect(result.warnings).toEqual([]);
  });

  it("warns about a screening at a place no venue owns", () => {
    const edited = page();
    edited.data[0]!["location"] = { "@id": "https://api.hel.fi/linkedevents/v1/place/tprek:1/" };
    const result = parseLinkedEvents(snapshot({ pages: [edited] }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["unclaimed-place"]);
  });
});

describe("parseLinkedEvents: Kannusali (Espoo's instance)", () => {
  const KANNUSALI = LINKED_EVENTS_SITES.find((s) => s.provider === "kannusali")!;
  const event = (name: string, id: string) => ({
    id,
    name: { fi: name },
    start_time: "2026-11-04T12:00:00Z",
    event_status: "EventScheduled",
    location: {
      "@id": "https://espooevents.prod.espoon-voltti.fi/api/events/v1/place/tprek:21430/",
    },
    offers: [{ is_free: true, price: null, info_url: null }],
    info_url: null,
  });
  const batch = parseLinkedEvents(
    snapshot({
      pages: [
        {
          meta: { next: null },
          data: [
            event("Elokuva: Kevlarsjäl (K12)", "espooevents:agqam3geym"),
            event("Lasten viikonloppu, Elokuva: Flow. (K7)", "espooevents:agqaw7ipcm"),
            event("Lumiukko - Elokuvakonsertti", "espooevents:agqbi7fj4u"),
            event("Teatteri Rajapinta: Monttu auki", "espooevents:agqopjlyuy"),
          ],
        },
      ],
    }),
    KANNUSALI,
  );

  it("keeps the labelled films and the film concert, not the play", () => {
    expect(batch.warnings).toEqual([]);
    expect(batch.listings.map((l) => [l.title.fi, l.rating, l.kind])).toEqual([
      ["Kevlarsjäl", "K-12", "film"],
      ["Flow.", "K-7", "film"],
      ["Lumiukko", undefined, "event"],
    ]);
    expect(batch.screenings.find((s) => s.sourceId === "espooevents:agqaw7ipcm")?.tags).toEqual([
      "kids",
    ]);
    expect(batch.screenings[0]?.price).toEqual({ amountCents: 0, currency: "EUR" });
  });
});

describe("parseLinkedEvents: Kanneltalo and Vuotalo (credited titles)", () => {
  const site = LINKED_EVENTS_SITES.find((s) => s.provider === "helsinginkulttuuritalot")!;
  const batch = parseLinkedEvents(
    snapshot({ days: 60, pages: [loadFixture("linkedevents", "kulttuuritalot-events.json")] }),
    site,
  );
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const titleOf = (id: string) => batch.listings.find((l) => l.id === show(id).listingId)?.title.fi;

  it("reads the labelled strands only, not school screenings or festivals", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.screenings.map((s) => s.sourceId).toSorted()).toEqual([
      "kulke:68960",
      "kulke:69568",
      "kulke:69579",
    ]);
  });

  it("drops the director from either end of the title", () => {
    expect(titleOf("kulke:68960")).toBe("Isänpäivä");
    expect(titleOf("kulke:69579")).toBe("Lapin sota");
    expect(titleOf("kulke:69568")).toBe("Presidentin kyyditys");
  });

  it("places each strand in its house", () => {
    expect(show("kulke:68960")).toMatchObject({
      venueId: "helsinginkulttuuritalot:venue:kanneltalo",
      series: ["Kino Kuutamo"],
      price: { amountCents: 0 },
    });
    expect(show("kulke:69568")).toMatchObject({
      venueId: "helsinginkulttuuritalot:venue:vuotalo",
      series: ["HopeaCine"],
      tags: ["senior"],
      price: { amountCents: 1000 },
    });
  });
});

describe("withoutCredits", () => {
  it.each([
    ["Aleksi Salmenperä: Isänpäivä", "Isänpäivä"],
    ["Pamela Tola: Teräsleidit – kuin viimeistä päivää", "Teräsleidit – kuin viimeistä päivää"],
    ["Lapin sota, ohj. Aku Louhimies", "Lapin sota"],
    // One word before the colon is a title, not a name.
    ["Dyyni: Osa kaksi", "Dyyni: Osa kaksi"],
    ["Tony", "Tony"],
  ])("%s -> %s", (raw, expected) => {
    expect(withoutCredits(raw)).toBe(expected);
  });
});
