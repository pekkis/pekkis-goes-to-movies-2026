import { z } from "zod";

/**
 * The Events Calendar (WordPress, "tribe") REST route,
 * `{base}/?rest_route=/tribe/events/v1/events`: public, no key. Only fields we read.
 * Profiled 2026-10-14 at Ritz Vaasa and Muhos.
 */
export const TribeEvent = z.looseObject({
  id: z.number().int(),
  /** May carry HTML entities. */
  title: z.string(),
  /** Local wall-clock time: "2026-10-18 13:00:00". */
  start_date: z.string(),
  /** The same instant in UTC: "2026-10-18 10:00:00". */
  utc_start_date: z.string(),
  all_day: z.boolean().optional(),
  categories: z.array(z.looseObject({ id: z.number().int() })),
  /** `values`: one is this event's price; several are a band ("10€ – 12€"). */
  cost_details: z.looseObject({ values: z.array(z.string()).optional() }).nullish(),
  /** The event's own page on the site. */
  url: z.string(),
  /** HTML; only its labelled lines are read ("Language: German", "Ikäraja sallittu."). */
  description: z.string().nullish(),
});
export type TribeEvent = z.infer<typeof TribeEvent>;

export const TribePage = z.looseObject({
  events: z.array(z.unknown()),
  total_pages: z.number().int().optional(),
});

export type TribeRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** Every page of the category's events in the window, in order. */
  pages: unknown[];
};
