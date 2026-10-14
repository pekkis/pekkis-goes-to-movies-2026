import type { HttpClient } from "../../lib/http.ts";
import { filmPages } from "./parse.ts";
import type { TapiolaSite } from "./sites.ts";

export type TapiolaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** `/elokuvat/`: one block per screening. */
  listing: string;
  /** Run page URL -> its HTML, one per distinct title in the window; null when it failed. */
  films: Record<string, string | null>;
};

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 40;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: the programme list, then one run page per title in the window (every run of
 * a title has the same page). The Johku ticket widgets on those pages are never called.
 */
export const fetchTapiola = async (
  http: HttpClient,
  site: TapiolaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<TapiolaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const listing = await http.getText(`${site.base}/elokuvat/`);
  const urls = filmPages(listing, site, from, days);
  if (urls.length > PAGE_BUDGET) {
    throw new Error(`${site.base}: ${urls.length} film pages exceeds the budget of ${PAGE_BUDGET}`);
  }
  const films: Record<string, string | null> = {};
  for (const url of urls) {
    // A missing page costs the film's details, not its screenings: the parser warns.
    films[url] = await http.getText(url).catch(() => null);
  }
  return { fetchedAt, from, days, listing, films };
};
