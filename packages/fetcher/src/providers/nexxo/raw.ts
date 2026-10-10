import { z } from "zod";

/**
 * Nexxo Scope `public_api.php?action=exportdailyshows` response. Only fields we read;
 * the rest passes through. Profiled 2026-10-10 over 214 shows on 10 locations.
 * Every value arrives as a string.
 */

export const RawShow = z.looseObject({
  showId: z.string(),
  movieId: z.string(),
  movieTitle: z.string(),
  /** Local Helsinki time, "2026-10-10 15:00:00". */
  startTime: z.string(),
  startDate: z.string().nullish(),
  roomId: z.string().nullish(),
  roomTitle: z.string().nullish(),
  /** "12", "S", "s", "Tapahtuma K18", "" */
  ageLimit: z.string().nullish(),
  /** Minutes. */
  duration: z.string().nullish(),
  /** "komedia, seikkailu, perhe-elokuva", sometimes with English mixed in. */
  genre: z.string().nullish(),
  /** "13.00"; "0.00" means not set. */
  priceIncludingTax: z.string().nullish(),
  /** "FI", "EN", "SE" (= Swedish), "IW" (= Hebrew), "OV" (original version: unknown). */
  code_language: z.string().nullish(),
  /** "FI-SE", "XX" (no subtitles), "OV" (unknown). */
  code_subtitles: z.string().nullish(),
  /** "Tavallinen näytös" (regular), festival or series names, events. */
  showTypeTitle: z.string().nullish(),
  /** "2026", or a range such as "1937-1949" for a shorts programme. */
  release_year: z.string().nullish(),
  is3D: z.string().nullish(),
  isUpcoming: z.string().nullish(),
});
export type RawShow = z.infer<typeof RawShow>;

/** `shows` is keyed by date; an empty programme comes back as `[]`. */
export const ShowsResponse = z.looseObject({
  shows: z.union([z.record(z.string(), z.array(z.unknown())), z.array(z.unknown())]),
});

export type NexxoRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** locationId -> response */
  payloads: Record<string, unknown>;
};
