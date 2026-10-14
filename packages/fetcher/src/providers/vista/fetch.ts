import type { HttpClient } from "../../lib/http.ts";
import type { VistaRawSnapshot } from "./raw.ts";
import type { VistaSite } from "./sites.ts";

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET per area (or one for all); 31 days covers the whole published window. */
export const fetchVista = async (
  http: HttpClient,
  site: VistaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<VistaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const schedules: Record<string, unknown> = {};
  const url = `${site.base}/xml/Schedule/`;
  for (const area of site.areas ?? ["all"]) {
    const params = { ...(area !== "all" && { area: String(area) }), nrOfDays: "31" };
    // XML stays text here; the parser reads it.
    schedules[area] =
      site.format === "xml"
        ? await http.getText(`${url}?${new URLSearchParams(params)}`)
        : await http.getJson(url, params);
  }
  return { fetchedAt, from, days, schedules };
};
