import type { Screening } from "../lib/api.ts";
import { FilmName } from "./FilmName.tsx";
import { safeHref } from "../lib/links.ts";
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
const ScreeningRow = ({ s, showSeries }: { s: Screening; showSeries: boolean }) => {
  const languages = languageLine(s);
  const status = useShowStatus(s.startsAt);
  const ticketUrl = safeHref(s.ticketUrl);
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
          <FilmName film={s.film} />
          {s.film.rating && <span className={css.badge}>{s.film.rating}</span>}
          <Availability value={s.availability} />
        </div>
        <div className={css.meta}>
          <a href={venuePath(s.venue)}>{s.venue.name}</a>
          {s.auditorium && `, ${s.auditorium}`}
          {languages && ` · ${languages}`}
          {showSeries && s.series.length > 0 && ` · ${s.series.join(", ")}`}
        </div>
      </div>
      {ticketUrl && s.availability !== "sold-out" && status.ticketsOpen && (
        <a
          className={`${button({ tone: "ghost", size: "sm" })} ${css.tickets}`}
          href={ticketUrl}
          rel="external noopener"
        >
          {fi.tickets}
        </a>
      )}
    </li>
  );
};

/**
 * A day's screenings in time order, each with its live status. Live inside a `<ClockIsland>`.
 * `showSeries` adds each screening's series ("Neulekino") where several kinds are listed.
 */
export const ScreeningList = ({
  screenings,
  showSeries = false,
}: {
  screenings: readonly Screening[];
  showSeries?: boolean;
}) => (
  <ol role="list" className={css.list}>
    {screenings.map((s) => (
      <ScreeningRow key={s.id} s={s} showSeries={showSeries} />
    ))}
  </ol>
);
