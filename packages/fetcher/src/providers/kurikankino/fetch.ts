import type { HttpClient } from "../../lib/http.ts";
import type { KurikanKinoSite } from "./sites.ts";

export type KurikanKinoRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: one card per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchKurikanKino = async (
  http: HttpClient,
  site: KurikanKinoSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KurikanKinoRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
