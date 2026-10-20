import type { FilmOpening } from "../lib/api.ts";
import { filmPath } from "../lib/films.ts";
import { fi } from "../lib/text.ts";
import { formatShortDay } from "../lib/time.ts";
import * as css from "./Film.css.ts";
import { Poster } from "./Poster.tsx";

/** Poster cards linking to the films' pages, with each film's first showing. */
export const FilmGrid = ({ openings }: { openings: FilmOpening[] }) => (
  <div className={css.gridContainer}>
    <ul role="list" className={css.grid}>
      {openings.map(({ film, firstShowing }) => {
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
            <span className={css.cardMeta}>{fi.firstShowing(formatShortDay(firstShowing))}</span>
          </li>
        );
      })}
    </ul>
  </div>
);
