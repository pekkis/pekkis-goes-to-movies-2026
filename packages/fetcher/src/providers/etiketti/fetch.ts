import type { HttpClient } from "../../lib/http.ts";
import { filmLinks, isEmptyProgramme } from "./parse.ts";
import type { EtikettiRawSnapshot } from "./raw.ts";
import { baseOf, type EtikettiSite } from "./sites.ts";

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 120;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: the programme listing, then each film page it links (every film page carries
 * all of its screenings). GET only; `/salikartta` (the booking flow) is never requested.
 */
export const fetchEtiketti = async (
  http: HttpClient,
  site: EtikettiSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<EtikettiRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const base = baseOf(site);
  const listing = await http.getText(`${base}/elokuvat/ohjelmistossa`);
  const paths = filmLinks(listing);
  if (paths.length === 0 && !isEmptyProgramme(listing)) {
    throw new Error(
      `${base}: no film links and no "empty programme" notice; has the page changed?`,
    );
  }
  if (paths.length > PAGE_BUDGET) {
    throw new Error(`${base}: ${paths.length} film pages exceeds the budget of ${PAGE_BUDGET}`);
  }
  const films: Record<string, string> = {};
  for (const path of paths) films[path] = await http.getText(`${base}${path}`);
  return { fetchedAt, from, days, listing, films };
};
