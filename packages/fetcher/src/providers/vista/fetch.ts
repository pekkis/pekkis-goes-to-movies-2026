import type { HttpClient } from "../../lib/http.ts";
import type { VistaRawSnapshot } from "./raw.ts";
import type { VistaSite } from "./sites.ts";

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET per area; 31 days covers the whole published window. */
export const fetchVista = async (
  http: HttpClient,
  site: VistaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<VistaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const schedules: Record<string, unknown> = {};
  for (const area of site.areas) {
    schedules[area] = await http.getJson(`${site.base}/xml/Schedule/`, { area, nrOfDays: 31 });
  }
  return { fetchedAt, from, days, schedules };
};
