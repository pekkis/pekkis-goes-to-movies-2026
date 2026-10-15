import { addDays } from "@pgtm/model/time";
import type { HttpClient } from "../../lib/http.ts";
import type { MyCalendarSite } from "./sites.ts";

export type MyCalendarRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** `/wp-json/my-calendar/v1/events`: occurrences keyed by date. */
  events: unknown;
  /** The cinema's page, for its price; null when not read or failed. */
  info: string | null;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: the category's occurrences in the window, and the page with the price. */
export const fetchMyCalendar = async (
  http: HttpClient,
  site: MyCalendarSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<MyCalendarRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const events = await http.getJson(`${site.base}/wp-json/my-calendar/v1/events`, {
    from,
    to: addDays(from, days - 1),
    category: site.category,
  });
  // A page that will not answer costs the price, never the programme.
  const info = site.pricePattern ? await http.getText(site.info).catch(() => null) : null;
  return { fetchedAt, from, days, events, info };
};
