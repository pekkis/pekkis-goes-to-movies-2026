import type { HttpClient } from "../../lib/http.ts";
import type { NuorisokuvatSite } from "./sites.ts";

export type NuorisokuvatRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The films page: one block per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the films page. */
export const fetchNuorisokuvat = async (
  http: HttpClient,
  site: NuorisokuvatSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<NuorisokuvatRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
