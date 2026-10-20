import { addDays, isIsoDate } from "@pgtm/model/time";
import {
  filmDayScreenings,
  filmOpenings,
  filmsPlaying,
  getFilm,
  listVenues,
  type Api,
  type Film,
  type FilmOpening,
  type FilmPlaying,
  type Screening,
} from "./api.ts";
import { byTitle, filmIdOfSlug, filmPath } from "./films.ts";
import { dayOptions, providersOf, type Provider } from "./search.ts";
import { fi } from "./text.ts";
import { formatShortDay } from "./time.ts";

/** One of the film page's day links: a day and how many screenings it has. */
export type FilmDay = { date: string; count: number };

export type FilmPage =
  | {
      kind: "film";
      film: Film;
      path: string;
      date: string;
      days: FilmDay[];
      screenings: Screening[];
      providers: Record<string, Provider>;
    }
  /** The slug names this film by an old or different title: send to the canonical path. */
  | { kind: "redirect"; path: string };

/**
 * Data for /fi/elokuvat/{slug}: the film, its screenings on each of the next seven days
 * (for the day links), and those of the chosen day. Without a chosen day, the first of the
 * seven with screenings. Undefined for an unknown film or an unmatched listing.
 */
export const loadFilmPage = async (
  api: Api,
  slug: string,
  dateParam: string | null,
  today: string,
): Promise<FilmPage | undefined> => {
  const id = filmIdOfSlug(slug);
  const film = id ? await getFilm(api, id) : undefined;
  const path = film && filmPath(film);
  if (!film || !path) {
    return undefined;
  }
  if (path !== `/fi/elokuvat/${slug}`) {
    return { kind: "redirect", path };
  }
  const week = dayOptions(today);
  const asked = dateParam && isIsoDate(dateParam) ? dateParam : undefined;
  const dates = asked && !week.includes(asked) ? [...week, asked] : week;
  const [loaded, venues] = await Promise.all([
    Promise.all(dates.map((d) => filmDayScreenings(api, film.id, d))),
    listVenues(api),
  ]);
  const byDate = new Map(dates.map((d, i) => [d, loaded[i]!]));
  const days = week.map((date) => ({ date, count: byDate.get(date)!.length }));
  const date = asked ?? days.find((d) => d.count > 0)?.date ?? today;
  const screenings = byDate.get(date) ?? [];
  return {
    kind: "film",
    film,
    path,
    date,
    days,
    screenings,
    providers: providersOf(venues, screenings),
  };
};

export type FrontPage = {
  /** First showing still to come, in the next seven days. */
  coming: FilmOpening[];
  /** First shown in the past week, today included. */
  opened: FilmOpening[];
  /**
   * Re-runs playing in the next seven days: films with a `classic` screening (old films,
   * and the cinemas' own classics).
   */
  reruns: FilmPlaying[];
};

/**
 * The front page: new films (opening in the past week or the next seven days, still
 * playing in those seven days), and re-runs playing in them. A film opens on its Finnish
 * premiere when TMDB knows it, else on its first screening with us. A re-run is never "new": a
 * film with a `classic` screening this week goes to the re-runs only. Each list by title.
 */
export const loadFrontPage = async (api: Api, today: string): Promise<FrontPage> => {
  const week = { from: today, to: addDays(today, 6) };
  const [openings, reruns] = await Promise.all([
    filmOpenings(api, addDays(today, -7), week.to, week, "classic"),
    filmsPlaying(api, week.from, week.to, "classic"),
  ]);
  const sorted = openings.toSorted((a, b) => byTitle(a.film, b.film));
  return {
    coming: sorted.filter((o) => o.opening > today),
    opened: sorted.filter((o) => o.opening <= today),
    reruns: reruns.toSorted((a, b) => byTitle(a.film, b.film)),
  };
};

/** A new film's card note: "ensi-ilta pe 23.10." on its Finnish premiere, else its first showing. */
export const openingNote = (o: FilmOpening): string =>
  o.finnishPremiere === o.opening
    ? fi.premiereOn(formatShortDay(o.opening))
    : fi.firstShowing(formatShortDay(o.opening));
