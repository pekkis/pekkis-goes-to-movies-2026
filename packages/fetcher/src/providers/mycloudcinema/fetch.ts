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
  for (const id of ids) {
    showtimes[id] = [];
    for (const window of windows(from, days, site.daysPerRequest)) {
      showtimes[id].push(
        await http.getJson(`${site.api}/show_times/getShowTimesDays`, {
          cinema_id: id,
          date: window.date,
          number_of_days: window.days,
        }),
      );
    }
  }

  return { fetchedAt, from, days, cinemas, showtimes };
};
