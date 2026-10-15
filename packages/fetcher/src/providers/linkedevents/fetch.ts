import { addDays } from "@pgtm/model/time";
import type { HttpClient } from "../../lib/http.ts";
import { LinkedEventsPage, type LinkedEventsRawSnapshot } from "./raw.ts";
import type { LinkedEventsSite } from "./sites.ts";

/** More pages than this means something is off: fail rather than hammer the API. */
export const PAGE_BUDGET = 10;

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: the venues' events in the window, following `meta.next` to the end. */
export const fetchLinkedEvents = async (
  http: HttpClient,
  site: LinkedEventsSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<LinkedEventsRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const pages: unknown[] = [];
  let payload = await http.getJson(site.api, {
    location: site.venues.map((v) => v.place).join(","),
    start: from,
    end: addDays(from, days - 1),
    page_size: 100,
    sort: "start_time",
  });
  for (;;) {
    pages.push(payload);
    const next = LinkedEventsPage.safeParse(payload).data?.meta.next;
    // `next` is the instance's own (canonical) address, which may differ from `api`.
    if (!next || !/^https:\/\/[^/]+\/(?:.+\/)?event\/\?/.test(next)) {
      break;
    }
    if (pages.length >= PAGE_BUDGET) {
      throw new Error(`${site.api}: more than ${PAGE_BUDGET} pages of events`);
    }
    payload = await http.getJson(next);
  }
  return { fetchedAt, from, days, pages };
};
