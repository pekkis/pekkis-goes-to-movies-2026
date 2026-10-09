import { addDays, formatISO, parseISO } from "date-fns";
import type { HttpClient } from "../../lib/http.ts";
import { RawSite, SitesResponse, type FinnkinoRawSnapshot } from "./raw.ts";

export const API = "https://digital-api.finnkino.fi/WSVistaWebClient/ocapi/v1";

export type FetchOptions = {
  /** First business date, `YYYY-MM-DD`. */
  from: string;
  days: number;
  /** Limit to these site ids (default: all). */
  siteIds?: string[];
  now?: () => Date;
};

export const businessDates = (from: string, days: number): string[] =>
  Array.from({ length: days }, (_, i) =>
    formatISO(addDays(parseISO(from), i), { representation: "date" }),
  );

/**
 * I/O only. `http` must already carry the token (see token.ts). One request for the
 * sites, then one per business date: each response covers every site and carries the
 * films, attributes and ratings it refers to.
 */
export const fetchFinnkino = async (
  http: HttpClient,
  { from, days, siteIds, now = () => new Date() }: FetchOptions,
): Promise<FinnkinoRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const sites = await http.getJson(`${API}/sites`);

  const ids =
    siteIds ??
    SitesResponse.parse(sites).sites.flatMap((item) => {
      const site = RawSite.safeParse(item);
      return site.success ? [site.data.id] : [];
    });
  const query = new URLSearchParams(ids.map((id) => ["siteIds", id])).toString();

  const showtimes: Record<string, unknown> = {};
  for (const date of businessDates(from, days)) {
    showtimes[date] = await http.getJson(`${API}/showtimes/by-business-date/${date}?${query}`);
  }

  return { fetchedAt, from, days, sites, showtimes };
};
