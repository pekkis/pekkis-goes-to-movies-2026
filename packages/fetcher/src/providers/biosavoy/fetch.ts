import type { HttpClient } from "../../lib/http.ts";
import type { BioSavoySite } from "./sites.ts";

export type BioSavoyRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: each hall's screenings. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchBioSavoy = async (
  http: HttpClient,
  site: BioSavoySite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<BioSavoyRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.base}/`);
  return { fetchedAt, from, days, html };
};
