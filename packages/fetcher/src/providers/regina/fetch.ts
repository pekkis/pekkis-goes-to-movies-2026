import type { HttpClient } from "../../lib/http.ts";
import { filmIds } from "./parse.ts";
import type { ReginaSite } from "./sites.ts";

export type ReginaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The endpoint's answer: the programme from `from` on, as HTML. */
  schedule: string;
  /** Film id -> its page (`/elokuva/{id}/`); null when it failed. */
  films: Record<string, string | null>;
};

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 60;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O: one form POST (the request the programme page makes), then one GET per film in the
 * window. The KAVI shop's ticket links are copied, never requested.
 */
export const fetchRegina = async (
  http: HttpClient,
  site: ReginaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<ReginaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const schedule = await http.postForm(site.schedule, { getShowtimesMovies: from });
  const ids = filmIds(schedule, from, days);
  if (ids.length > PAGE_BUDGET) {
    throw new Error(
      `${site.homepage}: ${ids.length} film pages exceeds the budget of ${PAGE_BUDGET}`,
    );
  }
  const films: Record<string, string | null> = {};
  for (const id of ids) {
    films[id] = await http.getText(`${site.homepage}/elokuva/${id}/`).catch(() => null);
  }
  return { fetchedAt, from, days, schedule, films };
};
