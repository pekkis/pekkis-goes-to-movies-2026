import type { HttpClient } from "../../lib/http.ts";
import type { KinoHuoviSite } from "./sites.ts";

export type KinoHuoviRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: one card per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchKinoHuovi = async (
  http: HttpClient,
  site: KinoHuoviSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KinoHuoviRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
