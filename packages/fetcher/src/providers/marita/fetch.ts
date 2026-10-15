import type { HttpClient } from "../../lib/http.ts";
import type { MaritaSite } from "./sites.ts";

export type MaritaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: one block per screening. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchMarita = async (
  http: HttpClient,
  site: MaritaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<MaritaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
