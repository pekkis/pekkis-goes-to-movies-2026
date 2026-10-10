import { differenceInCalendarDays, parseISO } from "date-fns";
import type { HttpClient } from "../../lib/http.ts";
import type { NexxoRawSnapshot } from "./raw.ts";
import type { NexxoSite } from "./sites.ts";

export const apiUrl = (site: NexxoSite): string =>
  `${site.apiBase ?? site.homepage}/wp-content/plugins/nexxo-scope/public_api.php`;

export type FetchOptions = {
  from: string;
  days: number;
  /** Today in Helsinki; the API always starts from today. */
  today: string;
  now?: () => Date;
};

/**
 * I/O only: one request per locationId (venues sharing a location share the request).
 * The API counts `days` from today, so a later `from` asks for more and the parser trims.
 */
export const fetchNexxo = async (
  http: HttpClient,
  site: NexxoSite,
  { from, days, today, now = () => new Date() }: FetchOptions,
): Promise<NexxoRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const span = Math.max(0, differenceInCalendarDays(parseISO(from), parseISO(today))) + days;
  const payloads: Record<string, unknown> = {};
  for (const locationId of new Set(site.venues.map((v) => v.locationId))) {
    payloads[locationId] = await http.getJson(apiUrl(site), {
      action: "exportdailyshows",
      locationid: locationId,
      days: span,
      lang: "fi",
      upcoming: 0,
    });
  }
  return { fetchedAt, from, days, payloads };
};
