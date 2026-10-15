import type { HttpClient } from "../../lib/http.ts";
import { filmUrls } from "./parse.ts";
import type { KisaKinoSite } from "./sites.ts";

export type KisaKinoRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: the films. */
  front: string;
  /** Film page URL -> its page; null when it failed. */
  films: Record<string, string | null>;
};

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 30;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: the front page, then each film's page. */
export const fetchKisaKino = async (
  http: HttpClient,
  site: KisaKinoSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KisaKinoRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const front = await http.getText(`${site.homepage}/`);
  const urls = filmUrls(front, site);
  if (urls.length > PAGE_BUDGET) {
    throw new Error(
      `${site.homepage}: ${urls.length} film pages exceeds the budget of ${PAGE_BUDGET}`,
    );
  }
  const films: Record<string, string | null> = {};
  for (const url of urls) {
    films[url] = await http.getText(url).catch(() => null);
  }
  return { fetchedAt, from, days, front, films };
};
