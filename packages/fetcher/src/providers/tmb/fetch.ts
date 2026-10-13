import type { HttpClient } from "../../lib/http.ts";
import type { TmbSite } from "./sites.ts";

export type TmbRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** `{base}/?lista=1`: the whole programme as a list. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: one GET per site. The film pages (`?ohjelmisto=`) would add runtime and price
 * at about one request per film; not read, to stay light on a small operator's server.
 */
export const fetchTmb = async (
  http: HttpClient,
  site: TmbSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<TmbRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.base}/?lista=1`);
  return { fetchedAt, from, days, html };
};
