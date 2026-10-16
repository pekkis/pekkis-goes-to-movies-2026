import type { HttpClient } from "../../lib/http.ts";
import type { BioDuxSite } from "./sites.ts";

export type BioDuxRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page, read as lines. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchBioDux = async (
  http: HttpClient,
  site: BioDuxSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<BioDuxRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
