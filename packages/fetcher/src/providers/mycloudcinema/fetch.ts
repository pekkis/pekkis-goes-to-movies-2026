import { addDays, daysBetween } from "@pgtm/model/time";
import type { HttpClient } from "../../lib/http.ts";
import { isActiveCinema } from "./parse.ts";
import { Envelope, RawCinema, type MyCloudCinemaRawSnapshot } from "./raw.ts";
import type { MyCloudCinemaSite } from "./sites.ts";

/** `getShowTimesDays` returns at most 7 days per request, whatever `number_of_days` asks. */
export const WINDOW_DAYS = 7;
/** At most this many times a short answer's tail is asked again, per cinema. */
const TAIL_ROUNDS = 4;

export type FetchOptions = {
  /** First business date, `YYYY-MM-DD`. */
  from: string;
  days: number;
  /** Limit to these cinema ids (default: the site's, else all active). */
  cinemaIds?: number[];
  now?: () => Date;
};

/** `[from, days]` split into windows of at most `size` days: 7 days is one request. */
export const windows = (
  from: string,
  days: number,
  size: number = WINDOW_DAYS,
): { date: string; days: number }[] =>
  Array.from({ length: Math.ceil(days / size) }, (_, i) => ({
    date: addDays(from, i * size),
    days: Math.min(size, days - i * size),
  }));

/** The business dates the answers have showtimes on. */
export const daysWithShows = (answers: unknown[]): Set<string> =>
  new Set(
    answers.flatMap((answer) => {
      const envelope = Envelope.safeParse(answer);
      return envelope.success
        ? envelope.data.data.flatMap((row) => {
            const date =
              row && typeof row === "object" && "business_date" in row
                ? String(row.business_date).slice(0, 10)
                : "";
            return /^\d{4}-\d{2}-\d{2}$/.test(date) ? [date] : [];
          })
        : [];
    }),
  );

/**
 * Days in `[from, from + days)` with no showtime in any answer, but before the last day
 * that has one: the gaps a truncated multi-day answer leaves.
 */
export const emptyDaysBefore = (answers: unknown[], from: string, days: number): string[] => {
  const seen = daysWithShows(answers);
  const last = [...seen].toSorted().at(-1);
  return last
    ? Array.from({ length: days }, (_, i) => addDays(from, i)).filter(
        (day) => day < last && !seen.has(day),
      )
    : [];
};

/**
 * The days after the last one with a showtime, up to the end of `[from, from + days)`: a
 * week's answer may also stop short at its end (BioRex Verkatehdas, 2026-10-23: 23.–25.10
 * of 23.–29.10). Undefined when the answers reach the end, or have no showtime at all.
 */
export const tailAfterLastShow = (
  answers: unknown[],
  from: string,
  days: number,
): { date: string; days: number } | undefined => {
  const last = [...daysWithShows(answers)].toSorted().at(-1);
  const end = addDays(from, days - 1);
  if (!last || last >= end) {
    return undefined;
  }
  const date = addDays(last, 1);
  return { date, days: daysBetween(date, end) + 1 };
};

/** I/O only: fetches raw responses without interpreting them beyond picking cinemas. */
export const fetchMyCloudCinema = async (
  http: HttpClient,
  site: MyCloudCinemaSite,
  { from, days, cinemaIds, now = () => new Date() }: FetchOptions,
): Promise<MyCloudCinemaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const cinemas = await http.getJson(`${site.api}/cinemas/getCinemasList`);

  const ids =
    cinemaIds ??
    site.cinemaIds ??
    Envelope.parse(cinemas).data.flatMap((item) => {
      const cinema = RawCinema.safeParse(item);
      return cinema.success && isActiveCinema(cinema.data) ? [cinema.data.cinema_id] : [];
    });

  const showtimes: Record<string, unknown[]> = {};
  const ask = (id: number, date: string, numberOfDays: number) =>
    http.getJson(`${site.api}/show_times/getShowTimesDays`, {
      cinema_id: id,
      date,
      number_of_days: numberOfDays,
    });
  for (const id of ids) {
    showtimes[id] = [];
    for (const window of windows(from, days, site.daysPerRequest)) {
      showtimes[id].push(await ask(id, window.date, window.days));
    }
    // A week's answer sometimes stops short: BioRex Verkatehdas' week came back with
    // three days (2026-10-22 and 23), while the rest, asked again, had 53 screenings.
    // First the tail after the last day with shows is asked again, while that brings new
    // days (a programme that really ends early costs one request); then each empty day
    // before the last is asked on its own (a closed day costs one request).
    for (let round = 0; round < TAIL_ROUNDS; round++) {
      const tail = tailAfterLastShow(showtimes[id], from, days);
      if (!tail) {
        break;
      }
      const known = daysWithShows(showtimes[id]).size;
      for (const window of windows(tail.date, tail.days, site.daysPerRequest)) {
        showtimes[id].push(await ask(id, window.date, window.days));
      }
      if (daysWithShows(showtimes[id]).size === known) {
        break;
      }
    }
    for (const day of emptyDaysBefore(showtimes[id], from, days)) {
      showtimes[id].push(await ask(id, day, 1));
    }
  }

  return { fetchedAt, from, days, cinemas, showtimes };
};
