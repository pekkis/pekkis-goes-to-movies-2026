import type { HttpClient } from "../../lib/http.ts";
import type { BioMarlonSite } from "./sites.ts";

export type BioMarlonRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The front page: one text block per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchBioMarlon = async (
  http: HttpClient,
  site: BioMarlonSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<BioMarlonRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
