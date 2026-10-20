import { filmPath } from "../lib/films.ts";

/** A film's title, linking to its page when it has one (TMDB films do; listings don't). */
export const FilmName = ({ film }: { film: { id: string; title: string } }) => {
  const path = filmPath(film);
  return path ? <a href={path}>{film.title}</a> : <>{film.title}</>;
};
