import type { HttpClient } from "../../lib/http.ts";
import { Envelope, RawCinema, type BiorexRawSnapshot } from "./raw.ts";
import { isActiveCinema } from "./parse.ts";

const API = "https://webshop.biorex.fi/webservices";

export type FetchOptions = {
  /** First business date, `YYYY-MM-DD`. */
  from: string;
  days: number;
  /** Limit to these cinema ids (default: all active). */
  cinemaIds?: number[];
  now?: () => Date;
};

/** I/O only: fetches raw responses without interpreting them beyond picking cinemas. */
export const fetchBiorex = async (
  http: HttpClient,
  { from, days, cinemaIds, now = () => new Date() }: FetchOptions,
): Promise<BiorexRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const cinemas = await http.getJson(`${API}/cinemas/getCinemasList`);

  const ids =
    cinemaIds ??
    Envelope.parse(cinemas).data.flatMap((item) => {
      const cinema = RawCinema.safeParse(item);
      return cinema.success && isActiveCinema(cinema.data) ? [cinema.data.cinema_id] : [];
    });

  const showtimes: Record<string, unknown> = {};
  for (const id of ids) {
    showtimes[id] = await http.getJson(`${API}/show_times/getShowTimesDays`, {
      cinema_id: id,
      date: from,
      number_of_days: days,
    });
  }

  return { fetchedAt, from, days, cinemas, showtimes };
};
