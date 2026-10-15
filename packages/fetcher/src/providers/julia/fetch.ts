import type { HttpClient } from "../../lib/http.ts";
import type { JuliaSite } from "./sites.ts";

export type JuliaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme page: every film with its screenings. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the programme page. */
export const fetchJulia = async (
  http: HttpClient,
  site: JuliaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<JuliaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
