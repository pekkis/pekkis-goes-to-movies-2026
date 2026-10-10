import type { HttpClient } from "../../lib/http.ts";
import { EventsPage, type KinolaRawSnapshot } from "./raw.ts";
import { apiBase, type KinolaSite } from "./sites.ts";

/** 500 events a page; more pages than this means something is off. */
export const MAX_PAGES = 5;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only: every upcoming event, following the API's `links.next`. The API returns all
 * future events (Kilta lists half a year ahead); the parser trims to the window.
 */
export const fetchKinola = async (
  http: HttpClient,
  site: KinolaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KinolaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const pages: unknown[] = [];
  let url: string | undefined = `${apiBase(site)}/events?limit=500`;
  while (url) {
    if (pages.length >= MAX_PAGES)
      throw new Error(`${site.tenant}: more than ${MAX_PAGES} pages of events`);
    const page = await http.getJson(url);
    pages.push(page);
    const next = EventsPage.safeParse(page).data?.links?.next;
    // Only follow links on the same API, never wherever a response points.
    url = next && next.startsWith(apiBase(site)) ? next : undefined;
  }
  return { fetchedAt, from, days, pages };
};
