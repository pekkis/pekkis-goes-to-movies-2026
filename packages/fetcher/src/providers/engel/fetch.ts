import type { HttpClient } from "../../lib/http.ts";
import type { EngelSite } from "./sites.ts";

export type EngelRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: every screening into the following months. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: one GET of the front page. A captcha challenge instead of the page fails the
 * pull, so the previous data stands; it is never solved or worked around.
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
  return { fetchedAt, from, days, html };
};
