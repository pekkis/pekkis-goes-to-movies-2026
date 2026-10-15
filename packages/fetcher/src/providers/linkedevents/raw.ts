import { z } from "zod";

/**
 * The City of Helsinki's Linked Events API (`https://api.hel.fi/linkedevents/v1/event/`):
 * open, GET, no key. Only fields we read. Profiled 2026-10-15 at Malmitalo (tprek:8740).
 */
const Text = z.looseObject({ fi: z.string().nullish() }).nullish();

export const LinkedEvent = z.looseObject({
  id: z.string(),
  name: Text,
  /** UTC: "2026-10-17T15:00:00Z". */
  start_time: z.string(),
  /** "EventScheduled", "EventRescheduled", "EventCancelled", "EventPostponed". */
  event_status: z.string().nullish(),
  deleted: z.boolean().nullish(),
  location: z.looseObject({ "@id": z.string() }).nullish(),
  offers: z
    .array(
      z.looseObject({
        is_free: z.boolean().nullish(),
        /** "9 €" */
        price: Text,
        /** The ticket page (lippu.fi), as the city publishes it. */
        info_url: Text,
      }),
    )
    .nullish(),
  /** The house's own event page. */
  info_url: Text,
});
export type LinkedEvent = z.infer<typeof LinkedEvent>;

export const LinkedEventsPage = z.looseObject({
  meta: z.looseObject({ next: z.string().nullish() }),
  data: z.array(z.unknown()),
});

export type LinkedEventsRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** Every page of the locations' events in the window, in order. */
  pages: unknown[];
};
