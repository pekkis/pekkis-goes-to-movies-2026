import type { HttpClient } from "../../lib/http.ts";
import { filmIds } from "./parse.ts";
import type { IsohannuSite } from "./sites.ts";

export type IsohannuRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: the week's show table. */
  html: string;
  /** Film id -> its `/leffasivu.php?id=` page; null when it failed. */
  films: Record<string, string | null>;
};

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 60;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: the front page, then each film page it links in the window. The ticket links
 * (`lipunmyynti.isohannu.fi`) are copied, never requested.
 */
export const fetchIsohannu = async (
  http: HttpClient,
  site: IsohannuSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<IsohannuRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.base}/`);
  const ids = filmIds(html, site, from, days);
  if (ids.length > PAGE_BUDGET) {
    throw new Error(`${site.base}: ${ids.length} film pages exceeds the budget of ${PAGE_BUDGET}`);
  }
  const films: Record<string, string | null> = {};
  for (const id of ids) {
    // A missing page costs the film's details, not its screenings: the parser warns.
    films[id] = await http.getText(`${site.base}/leffasivu.php?id=${id}`).catch(() => null);
  }
  return { fetchedAt, from, days, html, films };
};
