import type { Screening } from "../lib/api.ts";
import { tmdbUrl } from "../lib/films.ts";
import { fi, languageName } from "../lib/text.ts";
import { formatTime } from "../lib/time.ts";
import { venuePath } from "../lib/venues.ts";
import { button } from "../styles/recipes/button.css.ts";
import { useShowStatus } from "./clock.tsx";
import * as css from "./ScreeningList.css.ts";

/** "englanti, tekstit: suomi, ruotsi"; empty when the cinema says nothing. */
export const languageLine = (s: Pick<Screening, "audio" | "dubbed" | "subtitles">): string => {
  const parts: string[] = [];
  if (s.audio.length) {
    const audio = s.audio.map(languageName).join(", ");
    parts.push(s.dubbed ? `${fi.dubbed} ${audio}` : audio);
  }
  if (s.subtitles.kind === "none") {
    parts.push(fi.noSubtitles);
  } else if (s.subtitles.languages.length) {
    parts.push(fi.subtitles(s.subtitles.languages.map(languageName).join(", ")));
  }
  return parts.join(", ");
};

const Availability = ({ value }: { value: string }) =>
  value === "sold-out" ? (
    <span className={css.badge}>{fi.soldOut}</span>
  ) : value === "few-left" ? (
    <span className={css.badge}>{fi.fewLeft}</span>
  ) : null;

/** One screening: time with its live status, film, venue, languages and ticket link. */
const ScreeningRow = ({ s }: { s: Screening }) => {
  const languages = languageLine(s);
  const status = useShowStatus(s.startsAt);
  return (
    <li className={css.row} data-state={status.state}>
      <div>
        <time className={css.time} dateTime={s.startsAt}>
          {formatTime(s.startsAt)}
        </time>
        {status.label && <span className={css.status}>{status.label}</span>}
      </div>
      <div>
        <div className={css.title}>
          {s.film.kind === "film" ? <a href={tmdbUrl(s.film.id)}>{s.film.title}</a> : s.film.title}
          {s.film.rating && <span className={css.badge}>{s.film.rating}</span>}
          <Availability value={s.availability} />
        </div>
        <div className={css.meta}>
          <a href={venuePath(s.venue)}>{s.venue.name}</a>
          {s.auditorium && `, ${s.auditorium}`}
          {languages && ` · ${languages}`}
        </div>
      </div>
      {s.ticketUrl && s.availability !== "sold-out" && status.ticketsOpen && (
        <a
          className={`${button({ tone: "ghost", size: "sm" })} ${css.tickets}`}
          href={s.ticketUrl}
          rel="external noopener"
        >
          {fi.tickets}
        </a>
      )}
    </li>
  );
};

/** A day's screenings in time order, each with its live status. Live inside a `<ClockIsland>`. */
export const ScreeningList = ({ screenings }: { screenings: readonly Screening[] }) => (
  <ol role="list" className={css.list}>
    {screenings.map((s) => (
      <ScreeningRow key={s.id} s={s} />
    ))}
  </ol>
);
