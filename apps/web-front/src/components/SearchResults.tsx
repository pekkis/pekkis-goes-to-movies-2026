import { atom, useAtom } from "jotai";
import { useMemo, useState } from "react";
import type { Screening } from "../lib/api.ts";
import {
  applySelection,
  facetCounts,
  NOTHING_CHECKED,
  TIME_SLOTS,
  toggle,
  type Facet,
} from "../lib/facets.ts";
import { byTitle } from "../lib/films.ts";
import { fi } from "../lib/text.ts";
import { formatDay } from "../lib/time.ts";
import { button } from "../styles/recipes/button.css.ts";
import { ClockIsland } from "./clock.tsx";
import { ScreeningList } from "./ScreeningList.tsx";
import * as css from "./Search.css.ts";

/** The checked facet values; nothing checked shows everything. One per island store. */
const selectionAtom = atom(NOTHING_CHECKED);

type Option = { id: string; label: string; detail?: string };

/** One facet: a checkbox per value with how many screenings it would show. */
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
  // The detail too: a venue's city ("Tampere") finds its cinemas.
  const matches = (o: Option) =>
    `${o.label} ${o.detail ?? ""}`.toLocaleLowerCase("fi").includes(needle);
  const shown = needle ? options.filter((o) => checked.has(o.id) || matches(o)) : options;
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
        {shown.map((o) => {
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
        })}
      </ul>
    </details>
  );
};

/** The search results: facets beside (or, on a phone, above) the screenings by day. */
const Results = ({
  screenings,
  distances,
}: {
  screenings: Screening[];
  distances: Record<string, number>;
}) => {
  const [selection, setSelection] = useAtom(selectionAtom);
  const counts = useMemo(() => facetCounts(screenings, selection), [screenings, selection]);
  const shown = useMemo(() => applySelection(screenings, selection), [screenings, selection]);

  const venues = useMemo(() => {
    const unique = new Map(screenings.map((s) => [s.venue.id, s.venue]));
    return [...unique.values()]
      .map((v) => ({ ...v, km: distances[v.id] }))
      .toSorted((a, b) => (a.km ?? 0) - (b.km ?? 0) || a.name.localeCompare(b.name, "fi"))
      .map((v): Option => ({
        id: v.id,
        label: v.name,
        detail: v.km === undefined ? v.city : fi.km(v.km),
      }));
  }, [screenings, distances]);
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
  now,
}: {
  screenings: Screening[];
  distances: Record<string, number>;
  now: string;
}) => (
  <ClockIsland now={now}>
    <Results screenings={screenings} distances={distances} />
  </ClockIsland>
);
