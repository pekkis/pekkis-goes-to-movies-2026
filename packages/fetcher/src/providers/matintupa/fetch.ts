import type { HttpClient } from "../../lib/http.ts";
import type { MatinTupaSite } from "./sites.ts";

export type MatinTupaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme page: one block per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the programme page. */
export const fetchMatinTupa = async (
  http: HttpClient,
  site: MatinTupaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<MatinTupaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
