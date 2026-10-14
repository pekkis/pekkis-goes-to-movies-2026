import { addDays } from "@pgtm/model/time";
import type { HttpClient } from "../../lib/http.ts";
import { TribePage, type TribeRawSnapshot } from "./raw.ts";
import type { TribeSite } from "./sites.ts";

/** More pages than this means something is off: fail rather than hammer the site. */
export const PAGE_BUDGET = 10;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: the category's events in the window, every page of them. */
export const fetchTribe = async (
  http: HttpClient,
  site: TribeSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<TribeRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const pages: unknown[] = [];
  for (let page = 1; ; page += 1) {
    // `?rest_route=` works whatever the permalinks (Ritz serves its REST under a language).
    const payload = await http.getJson(`${site.base}/`, {
      rest_route: "/tribe/events/v1/events",
      per_page: 50,
      page,
      start_date: from,
      end_date: `${addDays(from, days - 1)} 23:59:59`,
      categories: site.category,
    });
    pages.push(payload);
    const total = TribePage.safeParse(payload).data?.total_pages ?? 1;
    if (page >= total) {
      break;
    }
    if (page >= PAGE_BUDGET) {
      throw new Error(`${site.base}: more than ${PAGE_BUDGET} pages of events`);
    }
  }
  return { fetchedAt, from, days, pages };
};
