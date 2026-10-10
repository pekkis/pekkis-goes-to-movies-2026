import { z } from "zod";

/**
 * Kinola public API (`https://{tenant}.kinola.ee/api/public/v1/events`), the endpoint
 * Kinola's own WordPress plugin reads (github.com/kinola-ee/kinola-wp, Kinola_Api.php).
 * Only fields we read; the rest passes through. Profiled 2026-10-10 over 260 events of
 * six tenants.
 */

const Production = z.looseObject({
  id: z.string(),
  name: z.string(),
  originalName: z.string().nullish(),
  /** Minutes. */
  duration: z.number().nullish(),
  year: z.number().int().nullish(),
  /** "K-12", "S", "L" (Estonian all-ages), "Not rated". */
  rating: z.string().nullish(),
  /** Finnish or English names, typos included: "englanti", "Polish", "ruotsi ". */
  languages: z.array(z.string()).nullish(),
  subtitles: z.array(z.string()).nullish(),
  distributor: z.string().nullish(),
  imdb_id: z.string().nullish(),
});

export const KinolaEvent = z.looseObject({
  id: z.string(),
  /** "2026-10-10T14:00:00+03:00" */
  local_time: z.string(),
  /** Free text: "Ensi-ilta", "Vapaa pääsy!", ticket terms. */
  note: z.string().nullish(),
  /** A series or a category ("Kahvikino", "Dokumentit"). */
  program: z.looseObject({ name: z.string() }).nullish(),
  venue: z.looseObject({ name: z.string() }),
  room: z.looseObject({ name: z.string() }).nullish(),
  freeSeats: z.number().int().nullish(),
  /** The cinema's own booking page for this show; copied, never constructed. */
  checkout_url: z.string().nullish(),
  price_range: z.looseObject({ min: z.number(), max: z.number(), currency: z.string() }).nullish(),
  /** "public", or "coming_soon" (listed, not on sale yet). */
  visibility: z.string().nullish(),
  production: Production,
});
export type KinolaEvent = z.infer<typeof KinolaEvent>;

export const EventsPage = z.looseObject({
  data: z.array(z.unknown()),
  links: z.looseObject({ next: z.string().nullish() }).nullish(),
});

export type KinolaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** One entry per API page. */
  pages: unknown[];
};
