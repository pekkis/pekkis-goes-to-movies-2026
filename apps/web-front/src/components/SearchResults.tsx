import { atom, useAtom } from "jotai";
import { useMemo, useState } from "react";
import type { Screening } from "../lib/api.ts";
import {
  applySelection,
  facetCounts,
  NOTHING_CHECKED,
  setAll,
  TIME_SLOTS,
  toggle,
  type Facet,
} from "../lib/facets.ts";
import { byTitle } from "../lib/films.ts";
import type { Provider } from "../lib/search.ts";
import { fi } from "../lib/text.ts";
import { formatDay } from "../lib/time.ts";
import { button } from "../styles/recipes/button.css.ts";
import { ClockIsland } from "./clock.tsx";
import { ScreeningList } from "./ScreeningList.tsx";
import * as css from "./Search.css.ts";

/** The checked facet values; nothing checked shows everything. One per island store. */
const selectionAtom = atom(NOTHING_CHECKED);

type Option = {
  id: string;
  label: string;
  detail?: string;
  /** The group it is listed under (a venue's provider), checkable as a whole. */
  group?: { id: string; label: string };
};

/** A row of a facet: one value, or a group of two or more values with its own checkbox. */
type Entry =
  | { kind: "one"; option: Option }
  | { kind: "group"; id: string; label: string; options: Option[] };

/**
 * Options in their order, a group's members gathered under it. A group with one member
 * (a cinema that is its own provider) is just that row.
 */
const entriesOf = (options: Option[], groupSizes: Map<string, number>): Entry[] => {
  const entries: Entry[] = [];
  const groups = new Map<string, Extract<Entry, { kind: "group" }>>();
  for (const option of options) {
    const g = option.group;
    if (!g || (groupSizes.get(g.id) ?? 0) < 2) {
      entries.push({ kind: "one", option });
      continue;
    }
    const existing = groups.get(g.id);
    if (existing) {
      existing.options.push(option);
    } else {
      const entry = { kind: "group" as const, id: g.id, label: g.label, options: [option] };
      groups.set(g.id, entry);
      entries.push(entry);
    }
  }
  return entries;
};

/** One facet: a checkbox per value (and per group) with how many screenings it would show. */
const FacetGroup = ({
  facet,
  legend,
  options,
  counts,
  filterable = false,
}: {
  facet: Facet;
  legend: string;
  options: Option[];
  counts: Map<string, number>;
  filterable?: boolean;
}) => {
  const [selection, setSelection] = useAtom(selectionAtom);
  const [filter, setFilter] = useState("");
  const checked = selection[facet] as ReadonlySet<string>;
  const needle = filter.trim().toLocaleLowerCase("fi");
  // The detail and the group too: "Tampere" finds a city's cinemas, "finnkino" a chain's.
  const matches = (o: Option) =>
    `${o.label} ${o.detail ?? ""} ${o.group?.label ?? ""}`.toLocaleLowerCase("fi").includes(needle);
  const shown = needle ? options.filter((o) => checked.has(o.id) || matches(o)) : options;
  const groupSizes = useMemo(() => {
    const sizes = new Map<string, number>();
    for (const o of options) {
      if (o.group) {
        sizes.set(o.group.id, (sizes.get(o.group.id) ?? 0) + 1);
      }
    }
    return sizes;
  }, [options]);

  const row = (o: Option) => {
    const count = counts.get(o.id) ?? 0;
    const isChecked = checked.has(o.id);
    return (
      <li key={o.id}>
        <label className={css.option} data-checked={isChecked || undefined}>
          <input
            type="checkbox"
            checked={isChecked}
            disabled={count === 0 && !isChecked}
            onChange={() => setSelection((s) => toggle(s, facet, o.id))}
          />
          <span>
            {o.label}
            {o.detail && <span className={css.muted}> · {o.detail}</span>}
          </span>
          <span className={css.count}>{count}</span>
        </label>
      </li>
    );
  };

  return (
    <details open className={css.facet}>
      <summary className={css.facetTitle}>
        {legend}
        {checked.size > 0 && ` (${checked.size})`}
      </summary>
      {filterable && (
        <input
          type="search"
          className={css.field}
          aria-label={`${legend}: ${fi.filterFilms}`}
          placeholder={fi.filterFilms}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      )}
      <ul role="list" className={css.options}>
        {entriesOf(shown, groupSizes).map((entry) => {
          if (entry.kind === "one") {
            return row(entry.option);
          }
          const ids = entry.options.map((o) => o.id);
          const all = ids.every((id) => checked.has(id));
          const some = !all && ids.some((id) => checked.has(id));
          const count = ids.reduce((sum, id) => sum + (counts.get(id) ?? 0), 0);
          return (
            <li key={`group:${entry.id}`}>
              <label className={css.option} data-checked={all || undefined}>
                <input
                  type="checkbox"
                  checked={all}
                  // Half-checked when some of the group's values are: the DOM property only.
                  ref={(el) => {
                    if (el) {
                      el.indeterminate = some;
                    }
                  }}
                  disabled={count === 0 && !all && !some}
                  onChange={() => setSelection((s) => setAll(s, facet, ids, !all))}
                />
                <span>{entry.label}</span>
                <span className={css.count}>{count}</span>
              </label>
              <ul role="list" className={css.nested}>
                {entry.options.map(row)}
              </ul>
            </li>
          );
        })}
      </ul>
    </details>
  );
};

/** The search results: facets beside (or, on a phone, above) the screenings by day. */
const Results = ({
  screenings,
  distances,
  providers,
}: {
  screenings: Screening[];
  distances: Record<string, number>;
  providers: Record<string, Provider>;
}) => {
  const [selection, setSelection] = useAtom(selectionAtom);
  const counts = useMemo(() => facetCounts(screenings, selection), [screenings, selection]);
  const shown = useMemo(() => applySelection(screenings, selection), [screenings, selection]);

  // By provider (a chain's venues together, so a season ticket's chain is one click), then
  // nearest first within it.
  const venues = useMemo(() => {
    const unique = new Map(screenings.map((s) => [s.venue.id, s.venue]));
    return [...unique.values()]
      .map((v) => ({ ...v, km: distances[v.id], provider: providers[v.id] }))
      .toSorted(
        (a, b) =>
          (a.provider?.name ?? a.name).localeCompare(b.provider?.name ?? b.name, "fi") ||
          (a.km ?? 0) - (b.km ?? 0) ||
          a.name.localeCompare(b.name, "fi"),
      )
      .map((v): Option => ({
        id: v.id,
        label: v.name,
        detail: v.km === undefined ? v.city : fi.km(v.km),
        ...(v.provider && { group: { id: v.provider.id, label: v.provider.name } }),
      }));
  }, [screenings, distances, providers]);
  const films = useMemo(
    () =>
      [...new Map(screenings.map((s) => [s.film.id, s.film])).values()]
        .toSorted(byTitle)
        .map((f): Option => ({ id: f.id, label: f.title })),
    [screenings],
  );
  const anyChecked = Object.values(selection).some((set) => set.size > 0);

  return (
    <div className={css.layoutContainer}>
      <div className={css.layout}>
        <section className={css.facets} aria-label={fi.narrow}>
          <a className={css.skip} href="#nayttokset">
            {fi.toResults(shown.length)}
          </a>
          <FacetGroup
            facet="slots"
            legend={fi.timeOfDay}
            options={TIME_SLOTS.map((slot) => ({ id: slot, label: fi.timeSlots[slot] }))}
            counts={counts.slots}
          />
          <FacetGroup
            facet="venues"
            legend={fi.venues}
            options={venues}
            counts={counts.venues}
            filterable={venues.length > 8}
          />
          <FacetGroup
            facet="films"
            legend={fi.filmsFacet}
            options={films}
            counts={counts.films}
            filterable={films.length > 8}
          />
          {anyChecked && (
            <button
              type="button"
              className={button({ tone: "ghost", size: "sm" })}
              onClick={() => setSelection(NOTHING_CHECKED)}
            >
              {fi.clear}
            </button>
          )}
        </section>
        <section id="nayttokset" className={css.results} aria-live="polite">
          <p className={css.summary}>{fi.screenings(shown.length)}</p>
          {shown.length === 0 ? (
            <p>{fi.noMatches}</p>
          ) : (
            [...Map.groupBy(shown, (s) => s.businessDate)].map(([day, shows]) => (
              <section key={day}>
                <h2 className={css.dayHeading}>
                  {formatDay(day)} · {fi.screenings(shows.length)}
                </h2>
                <ScreeningList screenings={shows} />
              </section>
            ))
          )}
        </section>
      </div>
    </div>
  );
};

/**
 * The search page's results as an island (`client:idle`): rendered on the server with
 * nothing checked, then the facets narrow the list in the browser without a reload.
 */
export const SearchResults = ({
  screenings,
  distances,
  providers = {},
  now,
}: {
  screenings: Screening[];
  distances: Record<string, number>;
  providers?: Record<string, Provider>;
  now: string;
}) => (
  <ClockIsland now={now}>
    <Results screenings={screenings} distances={distances} providers={providers} />
  </ClockIsland>
);
