import { z } from "zod";
import type { HttpClient } from "../../lib/http.ts";
import type { AlataloSite } from "./sites.ts";

export type AlataloRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme's HTML (a WordPress page's rendered content when read over REST). */
  html: string;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

const WpPages = z.array(z.looseObject({ content: z.looseObject({ rendered: z.string() }) })).min(1);

/** I/O only: one GET of the programme. */
export const fetchAlatalo = async (
  http: HttpClient,
  site: AlataloSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<AlataloRawSnapshot> => {
  const fetchedAt = now().toISOString();
  if (site.source.kind === "html") {
    return { fetchedAt, from, days, html: await http.getText(site.source.url) };
  }
  const pages = WpPages.safeParse(await http.getJson(site.source.url));
  if (!pages.success) {
    throw new Error(`${site.source.url}: not a WordPress page list`);
  }
  return { fetchedAt, from, days, html: pages.data[0]!.content.rendered };
};
