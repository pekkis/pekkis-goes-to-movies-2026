import type { HttpClient } from "../../lib/http.ts";
import type { LeviSummitSite } from "./sites.ts";

export type LeviSummitRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The cinema page: one section per day. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the cinema page. */
export const fetchLeviSummit = async (
  http: HttpClient,
  site: LeviSummitSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<LeviSummitRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
