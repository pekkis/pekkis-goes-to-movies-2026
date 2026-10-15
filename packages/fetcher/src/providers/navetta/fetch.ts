import type { HttpClient } from "../../lib/http.ts";
import type { NavettaSite } from "./sites.ts";

export type NavettaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: the weekend's screenings and the film blocks. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchNavetta = async (
  http: HttpClient,
  site: NavettaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<NavettaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
