import type { HttpClient } from "../../lib/http.ts";
import type { TervakoskiSite } from "./sites.ts";

export type TervakoskiRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme page. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the programme page. */
export const fetchTervakoski = async (
  http: HttpClient,
  site: TervakoskiSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<TervakoskiRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
