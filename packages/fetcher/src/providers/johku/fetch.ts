import type { HttpClient } from "../../lib/http.ts";
import type { JohkuRawSnapshot } from "./raw.ts";
import { scheduleUrl, type JohkuSite } from "./sites.ts";

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: one anonymous GET per programme block, with the parameters the storefront's
 * own code sends. The schedule runs from `from` onwards; the parser trims to the window.
 */
export const fetchJohku = async (
  http: HttpClient,
  site: JohkuSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<JohkuRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const schedules: Record<string, unknown> = {};
  for (const category of site.categories) {
    schedules[String(category)] = await http.getJson(scheduleUrl(site), {
      details: "true",
      storefront: "true",
      version: "fi_FI",
      from,
      category,
    });
  }
  return { fetchedAt, from, days, schedules };
};
