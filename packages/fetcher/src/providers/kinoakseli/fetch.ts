import type { HttpClient } from "../../lib/http.ts";
import type { KinoAkseliSite } from "./sites.ts";

export type KinoAkseliRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: every film with its facts and screenings. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: one GET of the front page. A captcha challenge instead of the page fails the
 * pull, so the previous data stands; it is never solved or worked around.
 */
export const fetchKinoAkseli = async (
  http: HttpClient,
  site: KinoAkseliSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KinoAkseliRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  if (!html.includes("Näytösajat") && /captcha/i.test(html)) {
    throw new Error(`${site.homepage}: answered with a captcha challenge; skipped`);
  }
  return { fetchedAt, from, days, html };
};
