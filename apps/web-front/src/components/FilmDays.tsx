import type { FilmDay } from "../lib/film-pages.ts";
import { fi } from "../lib/text.ts";
import { formatShortDay } from "../lib/time.ts";
import * as css from "./Film.css.ts";

/** The next seven days as links, each with its number of screenings; the chosen one marked. */
export const FilmDays = ({ days, date }: { days: FilmDay[]; date: string }) => (
  <nav aria-label={fi.screeningsByDay}>
    <ul role="list" className={css.days}>
      {days.map((d) => (
        <li key={d.date}>
          <a
            className={css.day}
            href={`?date=${d.date}`}
            {...(d.date === date && { "aria-current": "date" as const })}
          >
            {`${formatShortDay(d.date)} (${d.count})`}
          </a>
        </li>
      ))}
    </ul>
  </nav>
);
