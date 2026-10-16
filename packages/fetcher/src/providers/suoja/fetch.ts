import type { HttpClient } from "../../lib/http.ts";
import type { SuojaSite } from "./sites.ts";

export type SuojaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: one poster-info block per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchSuoja = async (
  http: HttpClient,
  site: SuojaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<SuojaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
