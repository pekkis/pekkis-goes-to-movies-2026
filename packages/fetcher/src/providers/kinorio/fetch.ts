import type { HttpClient } from "../../lib/http.ts";
import type { KinoRioSite } from "./sites.ts";

export type KinoRioRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: one block per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchKinoRio = async (
  http: HttpClient,
  site: KinoRioSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KinoRioRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
