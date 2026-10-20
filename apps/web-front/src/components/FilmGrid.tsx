import type { FilmSummary } from "../lib/api.ts";
import { filmPath } from "../lib/films.ts";
import * as css from "./Film.css.ts";
import { Poster } from "./Poster.tsx";

/**
 * Poster cards linking to the films' pages, each with a note under it: a new film's
 * premiere or first showing, a re-run's next one.
 */
export const FilmGrid = ({ films }: { films: { film: FilmSummary; note: string }[] }) => (
  <div className={css.gridContainer}>
    <ul role="list" className={css.grid}>
      {films.map(({ film, note }) => {
        const path = filmPath(film);
        const body = (
          <>
            <Poster url={film.posterUrl} title={film.title} size="md" />
            <span className={css.cardTitle}>{film.title}</span>
          </>
        );
        return (
          <li key={film.id} className={css.card}>
            {path ? (
              <a href={path} className={css.card}>
                {body}
              </a>
            ) : (
              body
            )}
            <span className={css.cardMeta}>{note}</span>
          </li>
        );
      })}
    </ul>
  </div>
);
