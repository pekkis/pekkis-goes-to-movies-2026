import type { Screening } from "../lib/api.ts";
import { groupByFilm, tmdbUrl } from "../lib/films.ts";
import { fi } from "../lib/text.ts";
import { formatTime } from "../lib/time.ts";
import { button } from "../styles/recipes/button.css.ts";
import * as css from "./FilmProgramme.css.ts";
import { languageLine } from "./ScreeningList.tsx";

/**
 * A venue's day, film by film: each film once, with its showtimes. Every showtime links to
 * the cinema's own ticket page. Static HTML: no client directive.
 */
export const FilmProgramme = ({ screenings }: { screenings: readonly Screening[] }) => (
  <ol role="list">
    {groupByFilm(screenings).map(({ film, screenings: shows }) => (
      <li key={film.id} className={css.film}>
        <h2 className={css.title}>
          {film.kind === "film" ? <a href={tmdbUrl(film.id)}>{film.title}</a> : film.title}
        </h2>
        <p className={css.facts}>
          {[film.rating, film.runtimeMinutes && fi.minutes(film.runtimeMinutes), film.year]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <ul role="list" className={css.shows}>
          {shows.map((s) => {
            const time = formatTime(s.startsAt);
            const details = [s.auditorium, languageLine(s)].filter(Boolean).join(" · ");
            const soldOut = s.availability === "sold-out";
            return (
              <li key={s.id} className={css.show}>
                {s.ticketUrl && !soldOut ? (
                  <a
                    className={button({ tone: "ghost", size: "sm" })}
                    href={s.ticketUrl}
                    rel="external noopener"
                    aria-label={fi.ticketsAt(time)}
                  >
                    <time className={css.time} dateTime={s.startsAt}>
                      {time}
                    </time>
                  </a>
                ) : (
                  <time className={css.time} dateTime={s.startsAt}>
                    {time}
                  </time>
                )}
                {soldOut && <span>{fi.soldOut}</span>}
                {s.availability === "few-left" && <span>{fi.fewLeft}</span>}
                {details && <span>{details}</span>}
              </li>
            );
          })}
        </ul>
      </li>
    ))}
  </ol>
);
