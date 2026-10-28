import type { HttpClient } from "../../lib/http.ts";
import { filmUrls } from "./parse.ts";
import type { BioSavoySite } from "./sites.ts";

export type BioSavoyRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** `/spelschema`: the programme, day by day. */
  schedule: string;
  /** Film page URL -> its page; null when it failed. */
  films: Record<string, string | null>;
};

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 30;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: the schedule, then each film's page. */
export const fetchBioSavoy = async (
  http: HttpClient,
  site: BioSavoySite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<BioSavoyRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const schedule = await http.getText(`${site.base}/spelschema`);
  const urls = filmUrls(schedule, site);
  if (urls.length > PAGE_BUDGET) {
    throw new Error(`${site.base}: ${urls.length} film pages exceeds the budget of ${PAGE_BUDGET}`);
  }
  const films: Record<string, string | null> = {};
  for (const url of urls) {
    films[url] = await http.getText(url).catch(() => null);
  }
  return { fetchedAt, from, days, schedule, films };
};
