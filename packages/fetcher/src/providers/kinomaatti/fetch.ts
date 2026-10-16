import type { HttpClient } from "../../lib/http.ts";
import type { KinomaattiSite } from "./sites.ts";

export type KinomaattiRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The page with the timetable. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the timetable page. */
export const fetchKinomaatti = async (
  http: HttpClient,
  site: KinomaattiSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KinomaattiRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
