import type { HttpClient } from "../../lib/http.ts";
import type { KaarreSite } from "./sites.ts";

export type KaarreRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The municipality's cinema page. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the cinema page. */
export const fetchKaarre = async (
  http: HttpClient,
  site: KaarreSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KaarreRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
