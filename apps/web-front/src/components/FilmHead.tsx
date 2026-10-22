import type { Film } from "../lib/api.ts";
import { tmdbUrl } from "../lib/films.ts";
import { fi } from "../lib/text.ts";
import { formatDate } from "../lib/time.ts";
import * as css from "./Film.css.ts";
import { Poster } from "./Poster.tsx";

/**
 * A film page's head: poster, titles, facts, synopsis and links, all from TMDB. Critics'
 * scores are not shown: they are opt-in everywhere.
 */
export const FilmHead = ({ film }: { film: Film }) => {
  const facts = [
    film.year,
    film.runtimeMinutes && fi.minutes(film.runtimeMinutes),
    film.rating,
    film.genres.join(", "),
  ].filter(Boolean);
  const overview = film.overview.fi ?? film.overview.en;
  const trailer = film.trailers.find((t) => t.site === "YouTube");
  return (
    <div className={css.headContainer}>
      <div className={css.head}>
        <Poster url={film.posterUrl} title={film.title} size="lg" eager />
        <div>
          <h1>{film.title}</h1>
          {film.originalTitle && film.originalTitle !== film.title && (
            <p className={css.facts}>{`${fi.originalTitle}: ${film.originalTitle}`}</p>
          )}
          {facts.length > 0 && <p className={css.facts}>{facts.join(" · ")}</p>}
          {film.directors.length > 0 && (
            <p className={css.facts}>
              {`${fi.directedBy}: ${film.directors.map((d) => d.name).join(", ")}`}
            </p>
          )}
          {film.collection && (
            <p className={css.facts}>{`${fi.filmSeries}: ${film.collection.name}`}</p>
          )}
          {film.finnishReleaseDate && (
            <p className={css.facts}>
              {`${fi.finnishPremiere}: ${formatDate(film.finnishReleaseDate)}`}
            </p>
          )}
          {overview && <p className={css.overview}>{overview}</p>}
          <p className={css.links}>
            {trailer && (
              <a href={`https://www.youtube.com/watch?v=${trailer.key}`} rel="external noopener">
                {fi.trailer}
              </a>
            )}
            <a href={tmdbUrl(film.id)} rel="external noopener">
              {fi.onTmdb}
            </a>
          </p>
        </div>
      </div>
    </div>
  );
};
