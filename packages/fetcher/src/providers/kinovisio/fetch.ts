import type { HttpClient } from "../../lib/http.ts";
import type { KinoVisioSite } from "./sites.ts";

export type KinoVisioRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: one paragraph per day. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchKinoVisio = async (
  http: HttpClient,
  site: KinoVisioSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KinoVisioRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
