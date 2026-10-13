import type { Screening } from "./api.ts";

export type FilmShows = { film: Screening["film"]; screenings: Screening[] };

/** A day's screenings grouped by film, films in order of their first show. */
export const groupByFilm = (screenings: readonly Screening[]): FilmShows[] => {
  const sorted = screenings.toSorted((a, b) => a.startsAt.localeCompare(b.startsAt));
  return [...Map.groupBy(sorted, (s) => s.film.id).values()].map((shows) => ({
    film: shows[0]!.film,
    screenings: shows,
  }));
};

export const tmdbUrl = (filmId: string): string =>
  `https://www.themoviedb.org/movie/${filmId.slice("tmdb:".length)}`;
