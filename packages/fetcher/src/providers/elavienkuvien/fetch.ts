import type { HttpClient } from "../../lib/http.ts";
import { filmPaths } from "./parse.ts";
import type { ElavienkuvienSite } from "./sites.ts";

export type ElavienkuvienRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** `/ohjelmisto/`: the films. */
  listing: string;
  /** Film path ("ohjelmisto/tony/") -> its page; null when it failed. */
  films: Record<string, string | null>;
};

/** More film pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 40;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: the listing, then each film's page. The reservation links on those pages are
 * copied, never requested.
 */
export const fetchElavienkuvien = async (
  http: HttpClient,
  site: ElavienkuvienSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<ElavienkuvienRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const listing = await http.getText(new URL("ohjelmisto/", site.base).href);
  const paths = filmPaths(listing);
  if (paths.length > PAGE_BUDGET) {
    throw new Error(
      `${site.base}: ${paths.length} film pages exceeds the budget of ${PAGE_BUDGET}`,
    );
  }
  const films: Record<string, string | null> = {};
  for (const path of paths) {
    films[path] = await http.getText(new URL(path, site.base).href).catch(() => null);
  }
  return { fetchedAt, from, days, listing, films };
};
