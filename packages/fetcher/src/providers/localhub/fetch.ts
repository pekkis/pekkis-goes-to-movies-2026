import type { HttpClient } from "../../lib/http.ts";
import type { LocalhubSite } from "./sites.ts";

export type LocalhubRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The calendar's search for the hashtag: `{pages, count}`. */
  search: unknown;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the calendar's search, the request its own pages make. */
export const fetchLocalhub = async (
  http: HttpClient,
  site: LocalhubSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<LocalhubRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const search = await http.getJson(
    `${site.base}/api/collection/${site.collection}/content/general-search`,
    { lang: "fi", country: "FI", q: site.hashtag, mode: "event", sort: "score" },
  );
  return { fetchedAt, from, days, search };
};
