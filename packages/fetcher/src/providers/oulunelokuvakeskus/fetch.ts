import type { HttpClient } from "../../lib/http.ts";
import type { OulunElokuvakeskusSite } from "./sites.ts";

export type OulunElokuvakeskusRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme page: one table per show, a month at a time. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the programme page. */
export const fetchOulunElokuvakeskus = async (
  http: HttpClient,
  site: OulunElokuvakeskusSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<OulunElokuvakeskusRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
