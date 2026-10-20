import type { Screening } from "./api.ts";
import { citySlug } from "./cities.ts";

export type FilmShows = { film: Screening["film"]; screenings: Screening[] };

/** Finnish alphabetical order: Å, Ä and Ö after Z; case and accents don't split titles. */
const titleOrder = new Intl.Collator("fi", { sensitivity: "base", numeric: true });

/** Films listed by name: alphabetical by title, the rule for every list of films. */
export const byTitle = (a: { title: string }, b: { title: string }): number =>
  titleOrder.compare(a.title, b.title);

/**
 * A day's screenings grouped by film. Films are alphabetical by title (same titles by
 * their first show); each film's screenings are in time order.
 */
export const groupByFilm = (screenings: readonly Screening[]): FilmShows[] => {
  const sorted = screenings.toSorted((a, b) => a.startsAt.localeCompare(b.startsAt));
  return [...Map.groupBy(sorted, (s) => s.film.id).values()]
    .map((shows) => ({ film: shows[0]!.film, screenings: shows }))
    .toSorted((a, b) => byTitle(a.film, b.film));
};

export const tmdbUrl = (filmId: string): string =>
  `https://www.themoviedb.org/movie/${filmId.slice("tmdb:".length)}`;

/**
 * A TMDB film's page: `/fi/elokuvat/lapin-sota-1450460`. The number is the id; the title
 * only makes the URL readable, so a renamed film's old links still work (and redirect).
 * Unmatched listings have no page.
 */
export const filmPath = (film: { id: string; title: string }): string | undefined => {
  const tmdb = film.id.match(/^tmdb:(\d+)$/);
  if (!tmdb) {
    return undefined;
  }
  const slug = citySlug(film.title);
  return `/fi/elokuvat/${slug ? `${slug}-` : ""}${tmdb[1]}`;
};

/** The film id a film page's slug names (`lapin-sota-1450460` -> `tmdb:1450460`). */
export const filmIdOfSlug = (slug: string): string | undefined => {
  const n = slug.match(/(?:^|-)(\d+)$/)?.[1];
  return n ? `tmdb:${n}` : undefined;
};
