import type { HttpClient } from "../../lib/http.ts";
import type { HaminaSite } from "./sites.ts";

export type HaminaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The cinema's page: every film with its fields and screenings. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the cinema's page. */
export const fetchHamina = async (
  http: HttpClient,
  site: HaminaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<HaminaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
