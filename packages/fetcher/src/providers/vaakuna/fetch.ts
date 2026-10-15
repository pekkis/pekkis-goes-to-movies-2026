import type { HttpClient } from "../../lib/http.ts";
import type { VaakunaSite } from "./sites.ts";

export type VaakunaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: every film card with its screenings. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchVaakuna = async (
  http: HttpClient,
  site: VaakunaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<VaakunaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
