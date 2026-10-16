import type { HttpClient } from "../../lib/http.ts";
import type { KinoYlariSite } from "./sites.ts";

export type KinoYlariRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The municipality's cinema page. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the cinema page. */
export const fetchKinoYlari = async (
  http: HttpClient,
  site: KinoYlariSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KinoYlariRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
