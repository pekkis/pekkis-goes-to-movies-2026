import type { HttpClient } from "../../lib/http.ts";
import type { BioPallasSite } from "./sites.ts";

export type BioPallasRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: the programme. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchBioPallas = async (
  http: HttpClient,
  site: BioPallasSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<BioPallasRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
