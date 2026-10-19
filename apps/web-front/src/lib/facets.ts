import type { Screening } from "./api.ts";

/**
 * The search page's facets: time of day, venue and film. Each is a set of checked values;
 * an empty set means "all", so nothing checked shows everything. Pure functions, so the
 * island only keeps the sets.
 */
export const TIME_SLOTS = ["morning", "afternoon", "evening", "late"] as const;
export type TimeSlot = (typeof TIME_SLOTS)[number];

export type Selection = {
  slots: ReadonlySet<TimeSlot>;
  venues: ReadonlySet<string>;
  films: ReadonlySet<string>;
};
export type Facet = keyof Selection;

export const NOTHING_CHECKED: Selection = { slots: new Set(), venues: new Set(), films: new Set() };

/**
 * Before 12, 12–17, 17–21, 21 and later. `startsAt` carries Helsinki wall-clock time with
 * its offset ("2026-10-19T18:00:00+03:00"), so its hour is the hour on the cinema's clock.
 * A show after midnight belongs to the evening before (`businessDate`), so it is late.
 */
export const timeSlot = (s: Pick<Screening, "startsAt" | "businessDate">): TimeSlot => {
  if (s.startsAt.slice(0, 10) !== s.businessDate) {
    return "late";
  }
  const hour = Number(s.startsAt.slice(11, 13));
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : hour < 21 ? "evening" : "late";
};

const valueOf: { [F in Facet]: (s: Screening) => string } = {
  slots: timeSlot,
  venues: (s) => s.venue.id,
  films: (s) => s.film.id,
};

const FACETS = Object.keys(valueOf) as Facet[];

const passes = (s: Screening, selection: Selection, facet: Facet) => {
  const checked = selection[facet] as ReadonlySet<string>;
  return checked.size === 0 || checked.has(valueOf[facet](s));
};

/** The screenings every facet lets through. */
export const applySelection = (
  screenings: readonly Screening[],
  selection: Selection,
): Screening[] => screenings.filter((s) => FACETS.every((f) => passes(s, selection, f)));

export type FacetCounts = { [F in Facet]: Map<string, number> };

/**
 * For each facet value, how many screenings it would show with the *other* facets as they
 * are: checking a venue changes the films' counts, not the other venues'.
 */
export const facetCounts = (
  screenings: readonly Screening[],
  selection: Selection,
): FacetCounts => {
  const counts = { slots: new Map(), venues: new Map(), films: new Map() } as FacetCounts;
  for (const s of screenings) {
    for (const facet of FACETS) {
      if (FACETS.every((other) => other === facet || passes(s, selection, other))) {
        const value = valueOf[facet](s);
        counts[facet].set(value, (counts[facet].get(value) ?? 0) + 1);
      }
    }
  }
  return counts;
};

/** The selection with one value checked or unchecked. */
export const toggle = <F extends Facet>(
  selection: Selection,
  facet: F,
  value: string,
): Selection => {
  const next = new Set(selection[facet] as ReadonlySet<string>);
  if (next.has(value)) {
    next.delete(value);
  } else {
    next.add(value);
  }
  return { ...selection, [facet]: next };
};
