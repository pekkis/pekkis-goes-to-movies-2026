import { z } from "zod";

/**
 * Raw shapes of Finnkino's Vista OCAPI (`digital-api.finnkino.fi/WSVistaWebClient/ocapi/v1`).
 * Only fields we read are declared; everything else passes through (looseObject).
 * Profiled 2026-10-09 over 2,889 showtimes in 17 sites, 7 days; see docs/data-sources.md.
 */

/** Vista's localized text: Finnish in `text`, others in `translations`. */
export const Text = z.looseObject({
  text: z.string(),
  translations: z.array(z.looseObject({ languageTag: z.string(), text: z.string() })).nullish(),
});
export type Text = z.infer<typeof Text>;

export const RawSite = z.looseObject({
  id: z.string(),
  name: Text,
  location: z.looseObject({ latitude: z.number(), longitude: z.number() }).nullish(),
  contactDetails: z
    .looseObject({
      address: z
        .looseObject({
          line1: z.string().nullish(),
          /** Postal code in practice. */
          line2: z.string().nullish(),
          city: z.string().nullish(),
        })
        .nullish(),
    })
    .nullish(),
});
export type RawSite = z.infer<typeof RawSite>;

export const SitesResponse = z.looseObject({ sites: z.array(z.unknown()) });

export const RawShowtime = z.looseObject({
  /** e.g. "1004-5832" */
  id: z.string(),
  schedule: z.looseObject({
    businessDate: z.iso.date(),
    startsAt: z.iso.datetime({ offset: true }),
    endsAt: z.iso.datetime({ offset: true }).nullish(),
  }),
  isSoldOut: z.boolean(),
  filmId: z.string(),
  siteId: z.string(),
  screenId: z.string(),
  attributeIds: z.array(z.string()),
  requires3dGlasses: z.boolean().nullish(),
  /** "FilmAdvanceBookingRule" means: see the rule for when sales open. */
  restrictions: z.array(z.string()),
});
export type RawShowtime = z.infer<typeof RawShowtime>;

export const RawFilm = z.looseObject({
  /** e.g. "HO00000334" */
  id: z.string(),
  title: Text,
  censorRatingId: z.string().nullish(),
  /** Finnish release date. */
  releaseDate: z.string().nullish(),
  runtimeInMinutes: z.number().int().nullish(),
  genreIds: z.array(z.string()).nullish(),
});
export type RawFilm = z.infer<typeof RawFilm>;

export const RawAttribute = z.looseObject({
  id: z.string(),
  name: Text,
  /** The stable vocabulary: "2D", "FI-A", "SE-S", "Annisk_K18", "LUXE", ... */
  shortName: Text,
});
export type RawAttribute = z.infer<typeof RawAttribute>;

export const RawCensorRating = z.looseObject({
  id: z.string(),
  /** "S", "7 A", "12 VA", "16 P", "Tulossa" (pending), ... */
  classification: Text,
});

export const RawScreen = z.looseObject({ id: z.string(), name: Text });

export const RawGenre = z.looseObject({ id: z.string(), name: Text });

export const RawAdvanceBookingRule = z.looseObject({
  filmId: z.string(),
  siteId: z.string(),
  bookingPeriods: z.array(
    z.looseObject({
      startsAt: z.iso.datetime({ offset: true }),
      restriction: z.string(),
    }),
  ),
});
export type RawAdvanceBookingRule = z.infer<typeof RawAdvanceBookingRule>;

export const ShowtimesResponse = z.looseObject({
  businessDate: z.string().nullish(),
  showtimes: z.array(z.unknown()),
  relatedData: z.looseObject({
    films: z.array(z.unknown()).nullish(),
    attributes: z.array(z.unknown()).nullish(),
    censorRatings: z.array(z.unknown()).nullish(),
    screens: z.array(z.unknown()).nullish(),
    genres: z.array(z.unknown()).nullish(),
    filmAdvanceBookingRules: z.array(z.unknown()).nullish(),
  }),
});

/** What the fetch step stores on disk and the parser consumes. */
export type FinnkinoRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  sites: unknown;
  /** business date -> /showtimes/by-business-date response */
  showtimes: Record<string, unknown>;
};
