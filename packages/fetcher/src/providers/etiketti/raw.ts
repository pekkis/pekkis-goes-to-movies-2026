import { z } from "zod";

/**
 * What the parser extracts from eTiketti pages before mapping to the model. The pages are
 * HTML, so these are our own shapes; validating them catches a changed template early.
 */

export const ExtractedShow = z.object({
  /** `date-10.10.2026` class on the row: the calendar date. */
  date: z.string().regex(/^\d{1,2}\.\d{1,2}\.\d{4}$/),
  /** "18.40" -> "18:40". */
  time: z.string().regex(/^\d{2}:\d{2}$/),
  /** "JOENSUU | TAPIO | TAPIO 3"; absent when the row prints none. */
  place: z.string().optional(),
  /** "/salikartta?id=55741": copied as the ticket link, never requested. */
  ticketPath: z.string().startsWith("/salikartta?id=").optional(),
  priceText: z.string().optional(),
  seatsFree: z.number().int().nonnegative().optional(),
  seatsTotal: z.number().int().positive().optional(),
  tags: z.array(z.string()),
  /** The bar icon (anniskelu.svg) next to the tags. */
  licensedIcon: z.boolean(),
});
export type ExtractedShow = z.infer<typeof ExtractedShow>;

export const ExtractedFilm = z.object({
  /** From the path /elokuvat/{id}/{slug}. */
  sourceId: z.string().regex(/^\d+$/),
  title: z.string().min(1),
  /** "12", "S" from ikarajat/fi-12.svg. */
  age: z.string().optional(),
  /** Labelled facts: "Kesto" -> "2 h 9 min", "Kieli" -> "englanti", … */
  facts: z.record(z.string(), z.string()),
  genres: z.array(z.string()),
});
export type ExtractedFilm = z.infer<typeof ExtractedFilm>;

export type EtikettiRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** The programme listing's HTML. */
  listing: string;
  /** Film page path -> HTML. */
  films: Record<string, string>;
};
