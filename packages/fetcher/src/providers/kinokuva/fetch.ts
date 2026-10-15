import type { HttpClient } from "../../lib/http.ts";
import type { KinoKuvaSite } from "./sites.ts";

export type KinoKuvaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page (decoded by its stated charset): one table row per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchKinoKuva = async (
  http: HttpClient,
  site: KinoKuvaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KinoKuvaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
