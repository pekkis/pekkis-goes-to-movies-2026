import { z } from "zod";

/**
 * Vista's public web services (`{base}/xml/Schedule/`), which answer JSON by default: the
 * older open interface some Vista cinemas leave on, unlike Finnkino's token-guarded OCAPI.
 * Only fields we read. Profiled 2026-10-13 at Korjaamo Kino (13 shows over 31 days).
 */

const Language = z
  .looseObject({ Name: z.string().nullish(), ISOTwoLetterCode: z.string().nullish() })
  .nullish();

export const VistaShow = z.looseObject({
  ID: z.number().int(),
  EventID: z.number().int(),
  TheatreID: z.number().int(),
  Theatre: z.string().nullish(),
  TheatreAuditorium: z.string().nullish(),
  /** As the cinema lists it, labels included: "Kirjastokino: Misery". */
  Title: z.string(),
  OriginalTitle: z.string().nullish(),
  ProductionYear: z.number().int().nullish(),
  LengthInMinutes: z.number().int().nullish(),
  /** "K-12", "Sallittu", "Ei tiedossa" (unknown). */
  Rating: z.string().nullish(),
  /** "Trilleri", comma-separated. */
  Genres: z.string().nullish(),
  /** "Movie" so far. */
  EventType: z.string().nullish(),
  /** A festival or strand, e.g. "HelAFF"; often "". */
  EventSeries: z.string().nullish(),
  /** "2D", "3D". */
  PresentationMethod: z.string().nullish(),
  /** UTC: "2026-10-15T07:00:00Z". */
  dttmShowStartUTC: z.string(),
  dttmShowEndUTC: z.string().nullish(),
  /** The cinema's programme day at local midnight: "2026-10-15T00:00:00". */
  dtAccounting: z.string(),
  SpokenLanguage: Language,
  SubtitleLanguage1: Language,
  SubtitleLanguage2: Language,
  AvailableSeats: z.number().int().nullish(),
  TotalSeats: z.number().int().nullish(),
  /** The show's own ticket page on the cinema's site; copied, never constructed. */
  ShowURL: z.string().nullish(),
});
export type VistaShow = z.infer<typeof VistaShow>;

/** `Shows.Show` is a list (or one show on its own); an empty schedule has no shows. */
export const ScheduleResponse = z.looseObject({
  Shows: z
    .union([
      z.array(z.unknown()),
      z.looseObject({ Show: z.union([z.array(z.unknown()), z.unknown()]).nullish() }),
    ])
    .nullish(),
});

export type VistaRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** area id (or "all") -> `/xml/Schedule/?area={id}&nrOfDays=31`: parsed JSON, or XML text. */
  schedules: Record<string, unknown>;
};
