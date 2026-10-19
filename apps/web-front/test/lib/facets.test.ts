import { describe, expect, it } from "vitest";
import {
  applySelection,
  facetCounts,
  NOTHING_CHECKED,
  timeSlot,
  toggle,
  type Selection,
} from "../../src/lib/facets.ts";
import { screening } from "../fixtures.ts";

describe("timeSlot", () => {
  it.each([
    ["2026-10-13T10:30:00+03:00", "2026-10-13", "morning"],
    ["2026-10-13T12:00:00+03:00", "2026-10-13", "afternoon"],
    ["2026-10-13T16:59:00+03:00", "2026-10-13", "afternoon"],
    ["2026-10-13T17:00:00+03:00", "2026-10-13", "evening"],
    ["2026-10-13T21:15:00+03:00", "2026-10-13", "late"],
    // After midnight, on the evening before's programme.
    ["2026-10-14T00:30:00+03:00", "2026-10-13", "late"],
  ])("%s (programme day %s) -> %s", (startsAt, businessDate, slot) => {
    expect(timeSlot({ startsAt, businessDate })).toBe(slot);
  });
});

const film = (id: string, title: string) => ({ ...screening().film, id, title });
const venue = (id: string, name: string) => ({ id, name, city: "Tampere", geo: null });

// Plevna: Digger 18.00, Lapin sota 21.15; Atlas: Lapin sota 13.00.
const SHOWS = [
  screening({ id: "1", venue: venue("plevna", "Plevna"), film: film("digger", "Digger") }),
  screening({
    id: "2",
    startsAt: "2026-10-13T21:15:00+03:00",
    venue: venue("plevna", "Plevna"),
    film: film("lapin", "Lapin sota"),
  }),
  screening({
    id: "3",
    startsAt: "2026-10-13T13:00:00+03:00",
    venue: venue("atlas", "Atlas"),
    film: film("lapin", "Lapin sota"),
  }),
];

const select = (over: Partial<Record<keyof Selection, string[]>>): Selection =>
  ({
    slots: new Set(over.slots ?? []),
    venues: new Set(over.venues ?? []),
    films: new Set(over.films ?? []),
  }) as Selection;

describe("applySelection", () => {
  it("shows everything when nothing is checked", () => {
    expect(applySelection(SHOWS, NOTHING_CHECKED)).toHaveLength(3);
  });

  it("keeps what every facet lets through", () => {
    const ids = (sel: Selection) => applySelection(SHOWS, sel).map((s) => s.id);
    expect(ids(select({ venues: ["plevna"] }))).toEqual(["1", "2"]);
    expect(ids(select({ venues: ["plevna"], films: ["lapin"] }))).toEqual(["2"]);
    expect(ids(select({ slots: ["afternoon", "late"] }))).toEqual(["2", "3"]);
    expect(ids(select({ venues: ["atlas"], slots: ["evening"] }))).toEqual([]);
  });
});

describe("facetCounts", () => {
  it("counts each facet with the other facets applied, not its own", () => {
    const counts = facetCounts(SHOWS, select({ venues: ["plevna"] }));
    // Films only at Plevna now.
    expect(Object.fromEntries(counts.films)).toEqual({ digger: 1, lapin: 1 });
    // Venues still count every venue, so another can be added.
    expect(Object.fromEntries(counts.venues)).toEqual({ plevna: 2, atlas: 1 });
    expect(Object.fromEntries(counts.slots)).toEqual({ evening: 1, late: 1 });
  });
});

describe("toggle", () => {
  it("checks and unchecks one value, leaving the rest alone", () => {
    const once = toggle(NOTHING_CHECKED, "films", "digger");
    expect([...once.films]).toEqual(["digger"]);
    expect([...toggle(once, "films", "digger").films]).toEqual([]);
    expect(NOTHING_CHECKED.films.size).toBe(0);
  });
});
