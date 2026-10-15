import type { HttpClient } from "../../lib/http.ts";
import type { LieksaSite } from "./sites.ts";

export type LieksaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The one page: the programme section and the coming-soon section. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the front page. */
export const fetchLieksa = async (
  http: HttpClient,
  site: LieksaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<LieksaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(`${site.homepage}/`);
  return { fetchedAt, from, days, html };
};
