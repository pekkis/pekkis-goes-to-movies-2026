import type { HttpClient } from "../../lib/http.ts";
import type { CinemahouseSite } from "./sites.ts";

export type CinemahouseRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The site's front page: film tiles and every screening row. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. Reservation links are copied, never requested. */
export const fetchCinemahouse = async (
  http: HttpClient,
  site: CinemahouseSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<CinemahouseRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.base}/`);
  return { fetchedAt, from, days, html };
};
