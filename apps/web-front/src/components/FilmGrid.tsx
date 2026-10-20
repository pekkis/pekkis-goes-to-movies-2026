import type { FilmSummary } from "../lib/api.ts";
import { filmPath } from "../lib/films.ts";
import { formatShortDay } from "../lib/time.ts";
import * as css from "./Film.css.ts";
import { Poster } from "./Poster.tsx";

/**
 * Poster cards linking to the films' pages, each with a day under it: a new film's first
 * showing, a classic's next one (`label` words it).
 */
export const FilmGrid = ({
  films,
  label,
}: {
  films: { film: FilmSummary; day: string }[];
  label: (day: string) => string;
}) => (
  <div className={css.gridContainer}>
    <ul role="list" className={css.grid}>
      {films.map(({ film, day }) => {
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
            <span className={css.cardMeta}>{label(formatShortDay(day))}</span>
          </li>
        );
      })}
    </ul>
  </div>
);
