import type { Screening } from "../lib/api.ts";
import { groupByFilm } from "../lib/films.ts";
import { FilmName } from "./FilmName.tsx";
import { fi } from "../lib/text.ts";
import { formatTime } from "../lib/time.ts";
import { button } from "../styles/recipes/button.css.ts";
import * as css from "./FilmProgramme.css.ts";
import { useShowStatus } from "./clock.tsx";
import { languageLine } from "./ScreeningList.tsx";

/**
 * One showtime: the time is the ticket link (to the cinema's own page) while tickets are
 * sold, plain text after; with its live status, availability, hall and languages.
 */
export const Showtime = ({ s }: { s: Screening }) => {
  const status = useShowStatus(s.startsAt);
  const time = formatTime(s.startsAt);
  const details = [s.auditorium, languageLine(s)].filter(Boolean).join(" · ");
  const soldOut = s.availability === "sold-out";
  const plainTime = (
    <time className={css.time} dateTime={s.startsAt}>
      {time}
    </time>
  );
  return (
    <li className={css.show} data-state={status.state}>
      {s.ticketUrl && !soldOut && status.ticketsOpen ? (
        <a
          className={`${button({ tone: "ghost", size: "sm" })} ${css.ticket}`}
          href={s.ticketUrl}
          rel="external noopener"
          aria-label={fi.ticketsAt(time)}
        >
          {plainTime}
        </a>
      ) : (
        plainTime
      )}
      {status.label && <span className={css.status}>{status.label}</span>}
      {soldOut && <span>{fi.soldOut}</span>}
      {s.availability === "few-left" && <span>{fi.fewLeft}</span>}
      {details && <span>{details}</span>}
    </li>
  );
};

/**
 * A venue's day, film by film: each film once, alphabetically, with its showtimes in time
 * order and their live status. Live inside a `<ClockIsland>`.
 */
export const FilmProgramme = ({ screenings }: { screenings: readonly Screening[] }) => (
  <ol role="list">
    {groupByFilm(screenings).map(({ film, screenings: shows }) => (
      <li key={film.id} className={css.film}>
        <h2 className={css.title}>
          <FilmName film={film} />
        </h2>
        <p className={css.facts}>
          {[film.rating, film.runtimeMinutes && fi.minutes(film.runtimeMinutes), film.year]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <ul role="list" className={css.shows}>
          {shows.map((s) => (
            <Showtime key={s.id} s={s} />
          ))}
        </ul>
      </li>
    ))}
  </ol>
);
