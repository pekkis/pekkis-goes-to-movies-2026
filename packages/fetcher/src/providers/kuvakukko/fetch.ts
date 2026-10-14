import type { HttpClient } from "../../lib/http.ts";
import { filmPages } from "./parse.ts";
import type { KuvakukkoSite } from "./sites.ts";

export type KuvakukkoRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme page: both cinemas' schedules. */
  html: string;
  /** Film page URL -> its HTML, for the linked films in the window; null when it failed. */
  films: Record<string, string | null>;
};

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 40;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: the shared programme page, then each linked film page in the window. */
export const fetchKuvakukko = async (
  http: HttpClient,
  site: KuvakukkoSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KuvakukkoRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  const urls = filmPages(html, site, from, days);
  if (urls.length > PAGE_BUDGET) {
    throw new Error(
      `${site.programme}: ${urls.length} film pages exceeds the budget of ${PAGE_BUDGET}`,
    );
  }
  const films: Record<string, string | null> = {};
  for (const url of urls) {
    // A missing page costs the film's details, not its screenings: the parser warns.
    films[url] = await http.getText(url).catch(() => null);
  }
  return { fetchedAt, from, days, html, films };
};
