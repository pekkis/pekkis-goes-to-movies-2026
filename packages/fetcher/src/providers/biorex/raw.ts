import { z } from "zod";

/**
 * Raw response shapes of the BioRex webshop (MyCloudCinema) `/webservices` API.
 * Only fields we read are declared; everything else passes through (looseObject).
 * Profiled 2026-10-09 over 1044 showtimes in 12 cinemas, see docs/data-sources.md.
 */

const Flag = z.union([z.literal(0), z.literal(1)]);

export const RawCinema = z.looseObject({
  cinema_id: z.number().int(),
  cinema_name: z.string(),
  cinema_short_name: z.string().nullish(),
  offline: Flag,
  screen_count: z.number().int(),
  address: z.string().nullish(),
  city: z.string().nullish(),
  postal_code: z.string().nullish(),
  latitude: z.number().nullish(),
  longitude: z.number().nullish(),
});
export type RawCinema = z.infer<typeof RawCinema>;

export const RawShowtime = z.looseObject({
  show_time_id: z.number().int(),
  movie_id: z.number().int(),
  movie_version_id: z.number().int(),
  cinema_screen_id: z.number().int(),
  screen_name: z.string(),
  title: z.string(),
  /** Version label: "ATMOS", "FI DUB", "SWE DUB", "ORIG", "FI", "FI ATMOS" or null. */
  title_extension: z.string().nullable(),
  /** UTC, e.g. "2026-10-09T14:30:00.000Z". */
  show_time: z.iso.datetime(),
  show_time_end: z.iso.datetime().nullish(),
  /** Midnight UTC of the business date, e.g. "2026-10-09T00:00:00.000Z". */
  business_date: z.string(),
  running_time: z.number().int().nullish(),
  /** Rating icon file, e.g. "rating_fi_12.svg". */
  rating: z.string().nullish(),
  genre: z.string().nullish(),
  countries: z.string().nullish(),
  /** "FI", "EN", "SE" (= Swedish), ... */
  audio_lang: z.string().nullish(),
  /** "Suomi & Ruotsi -", "SE", "-" */
  subtitle_lang: z.string().nullish(),
  /** 1 = original language, 2 = dubbed. */
  movie_audio_style_id: z.number().int().nullish(),
  sold_out: Flag,
  seats_low: Flag,
  bookable: Flag,
  allow_purchases: Flag,
  show_locked: Flag,
  version_3d: Flag.optional(),
  version_16mm: Flag.optional(),
  version_35mm: Flag.optional(),
  version_70mm: Flag.optional(),
  version_atmos: Flag.optional(),
  version_dbox: Flag.optional(),
  version_imax: Flag.optional(),
  version_luxe: Flag.optional(),
  version_kids: Flag.optional(),
});
export type RawShowtime = z.infer<typeof RawShowtime>;

/** Every webservices response is wrapped like this. */
export const Envelope = z.looseObject({
  resultCode: z.number().optional(),
  data: z.array(z.unknown()),
});

/** What the fetch step stores on disk and the parser consumes. */
export type BiorexRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  cinemas: unknown;
  /** cinema_id -> getShowTimesDays response */
  showtimes: Record<string, unknown>;
};
