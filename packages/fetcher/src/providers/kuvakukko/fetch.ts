import type { HttpClient } from "../../lib/http.ts";
import type { KuvakukkoSite } from "./sites.ts";

export type KuvakukkoRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme page: both cinemas' schedules. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the shared programme page. */
export const fetchKuvakukko = async (
  http: HttpClient,
  site: KuvakukkoSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KuvakukkoRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
