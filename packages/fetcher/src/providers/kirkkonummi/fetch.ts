import type { HttpClient } from "../../lib/http.ts";
import type { KirkkonummiSite } from "./sites.ts";

export type KirkkonummiRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The one page: every film and its screenings. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchKirkkonummi = async (
  http: HttpClient,
  site: KirkkonummiSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KirkkonummiRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
