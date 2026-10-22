import { addDays } from "@pgtm/model/time";
import type { HttpClient } from "../../lib/http.ts";
import { isActiveCinema } from "./parse.ts";
import { Envelope, RawCinema, type MyCloudCinemaRawSnapshot } from "./raw.ts";
import type { MyCloudCinemaSite } from "./sites.ts";

/** `getShowTimesDays` returns at most 7 days per request, whatever `number_of_days` asks. */
export const WINDOW_DAYS = 7;

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

/**
 * Days in `[from, from + days)` with no showtime in any answer, but before the last day
 * that has one: the gaps a truncated multi-day answer leaves.
 */
export const emptyDaysBefore = (answers: unknown[], from: string, days: number): string[] => {
  const seen = new Set(
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
  const last = [...seen].toSorted().at(-1);
  return last
    ? Array.from({ length: days }, (_, i) => addDays(from, i)).filter(
        (day) => day < last && !seen.has(day),
      )
    : [];
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
    // A week's answer sometimes stops short: BioRex Verkatehdas' week from 2026-10-22
    // came back with three days, while the other four, asked alone, had 53 screenings.
    // Each empty day before the cinema's last day is asked once more on its own; a day
    // the cinema is really closed costs one request.
    for (const day of emptyDaysBefore(showtimes[id], from, days)) {
      showtimes[id].push(await ask(id, day, 1));
    }
  }

  return { fetchedAt, from, days, cinemas, showtimes };
};
