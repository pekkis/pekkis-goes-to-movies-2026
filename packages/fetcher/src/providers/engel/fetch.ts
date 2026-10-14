import type { HttpClient } from "../../lib/http.ts";
import { filmPages } from "./parse.ts";
import type { EngelSite } from "./sites.ts";

export type EngelRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: every screening into the following months. */
  html: string;
  /** Film page URL -> its HTML, for the films in the window; null when it failed. */
  films: Record<string, string | null>;
};

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 40;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: the front page, then each film page in the window (runtime, languages,
 * original title). A captcha challenge instead of the front page fails the pull, so the
 * previous data stands; it is never solved or worked around.
 */
export const fetchEngel = async (
  http: HttpClient,
  site: EngelSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<EngelRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.base}/`);
  if (!html.includes("rs-johku-movies") && /captcha/i.test(html)) {
    throw new Error(`${site.base}: answered with a captcha challenge; skipped`);
  }
  const urls = filmPages(html, site, from, days);
  if (urls.length > PAGE_BUDGET) {
    throw new Error(`${site.base}: ${urls.length} film pages exceeds the budget of ${PAGE_BUDGET}`);
  }
  const films: Record<string, string | null> = {};
  for (const url of urls) {
    // A missing page costs the film's details, not its screenings: the parser warns.
    films[url] = await http.getText(url).catch(() => null);
  }
  return { fetchedAt, from, days, html, films };
};
