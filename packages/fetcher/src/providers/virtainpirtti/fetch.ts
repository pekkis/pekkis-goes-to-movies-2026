import type { HttpClient } from "../../lib/http.ts";
import type { VirtainPirttiSite } from "./sites.ts";

export type VirtainPirttiRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme page: one paragraph per film. */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the programme page. */
export const fetchVirtainPirtti = async (
  http: HttpClient,
  site: VirtainPirttiSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<VirtainPirttiRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const html = await http.getText(site.programme);
  return { fetchedAt, from, days, html };
};
