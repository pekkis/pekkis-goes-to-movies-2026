import { z } from "zod";

/**
 * Domain model. Single source of truth: TypeScript types are inferred from these
 * schemas and the published JSON Schema is generated from them.
 * See docs/data-model.md.
 */

export const ProviderId = z.string().regex(/^[a-z0-9-]+$/);
export type ProviderId = z.infer<typeof ProviderId>;

export const EntityKind = z.enum(["venue", "screen", "film", "show"]);
export type EntityKind = z.infer<typeof EntityKind>;

/** Namespaced id: `{provider}:{kind}:{sourceId}`, e.g. `biorex:show:436478`. */
export const Id = z.string().regex(/^[a-z0-9-]+:(venue|screen|film|show):[^:\s]+$/);
export type Id = z.infer<typeof Id>;

export const makeId = (provider: ProviderId, kind: EntityKind, sourceId: string | number): Id =>
  `${provider}:${kind}:${sourceId}`;

/** ISO 639-1, lowercase. `zxx` = no linguistic content. */
export const Lang = z.string().regex(/^([a-z]{2}|zxx)$/);
export type Lang = z.infer<typeof Lang>;

export const FinnishRating = z.enum(["S", "K-7", "K-12", "K-16", "K-18"]);
export type FinnishRating = z.infer<typeof FinnishRating>;

export const Localized = z.object({
  fi: z.string().optional(),
  sv: z.string().optional(),
  en: z.string().optional(),
});
export type Localized = z.infer<typeof Localized>;

/** Wall-clock time with offset, e.g. `2026-10-09T20:00:00+03:00`. */
const OffsetDateTime = z.iso.datetime({ offset: true });
const IsoDate = z.iso.date();

export const Platform = z.enum([
  "vista-ocapi",
  "mycloudcinema",
  "etiketti",
  "nexxo",
  "johku",
  "custom",
]);

export const Provider = z.object({
  id: ProviderId,
  name: z.string(),
  homepage: z.url(),
  platform: Platform,
  /** What the ticket link leads to. */
  booking: z.enum(["buy", "reserve", "door", "info"]),
});
export type Provider = z.infer<typeof Provider>;

export const Venue = z.object({
  id: Id,
  provider: ProviderId,
  sourceId: z.string(),
  name: z.string(),
  shortName: z.string().optional(),
  city: z.string().min(1),
  address: z.string().optional(),
  postalCode: z.string().optional(),
  geo: z.object({ lat: z.number(), lon: z.number() }).optional(),
  url: z.url().optional(),
});
export type Venue = z.infer<typeof Venue>;

export const Feature = z.enum([
  "imax",
  "isense",
  "4dx",
  "screenx",
  "dbox",
  "atmos",
  "luxe",
  "plus",
  "prime",
]);
export type Feature = z.infer<typeof Feature>;

export const Auditorium = z.object({
  id: Id,
  venueId: Id,
  name: z.string(),
  seats: z.number().int().positive().optional(),
  features: z.array(Feature),
  /** Age limit the auditorium itself imposes (e.g. a licensed K-18 hall). */
  ageLimit: FinnishRating.optional(),
});
export type Auditorium = z.infer<typeof Auditorium>;

/** A provider's own film record, normalized but not merged across providers. */
export const FilmListing = z.object({
  id: Id,
  provider: ProviderId,
  sourceId: z.string(),
  title: Localized,
  originalTitle: z.string().optional(),
  year: z.number().int().optional(),
  runtimeMinutes: z.number().int().positive().optional(),
  rating: FinnishRating.optional(),
  genres: z.array(z.string()),
  /** Production countries as the provider writes them (e.g. Finnish names). */
  countries: z.array(z.string()),
  /** Canonical film (`tmdb:{id}`), set by the matching step. */
  filmId: z.string().optional(),
  /** How `filmId` was decided. */
  match: z.enum(["auto", "alias"]).optional(),
});
export type FilmListing = z.infer<typeof FilmListing>;

/**
 * Canonical film from TMDB. Posters, synopses and trailers come only from here,
 * never from cinemas. Image paths are TMDB paths: `https://image.tmdb.org/t/p/{size}{path}`.
 */
export const Film = z.object({
  id: z.string().regex(/^tmdb:\d+$/),
  tmdbId: z.number().int().positive(),
  imdbId: z.string().optional(),
  title: Localized,
  originalTitle: z.string(),
  originalLanguage: Lang.optional(),
  /** World premiere date (TMDB `release_date`). */
  releaseDate: IsoDate.optional(),
  /** Earliest Finnish theatrical release. */
  finnishReleaseDate: IsoDate.optional(),
  runtimeMinutes: z.number().int().positive().optional(),
  /** Finnish age rating (KAVI) as recorded in TMDB. */
  rating: FinnishRating.optional(),
  /** Genre names in Finnish. */
  genres: z.array(z.string()),
  /** ISO 3166-1 alpha-2. */
  countries: z.array(z.string().regex(/^[A-Z]{2}$/)),
  overview: Localized,
  posterPath: z.string().startsWith("/").optional(),
  backdropPath: z.string().startsWith("/").optional(),
  trailers: z.array(
    z.object({
      site: z.literal("YouTube"),
      key: z.string(),
      name: z.string(),
      language: Lang.optional(),
    }),
  ),
  fetchedAt: z.iso.datetime(),
});
export type Film = z.infer<typeof Film>;

/** A listing the matcher could not link with confidence; input for the alias file. */
export const Unmatched = z.object({
  listingId: Id,
  title: z.string(),
  reason: z.string(),
  candidates: z.array(
    z.object({ tmdbId: z.number().int(), title: z.string(), year: z.number().int().optional() }),
  ),
});
export type Unmatched = z.infer<typeof Unmatched>;

export const FilmCatalog = z.object({
  generatedAt: z.iso.datetime(),
  films: z.array(Film),
  unmatched: z.array(Unmatched),
});
export type FilmCatalog = z.infer<typeof FilmCatalog>;

export const Subtitles = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("none") }),
  z.object({ kind: z.literal("unknown-language") }),
  z.object({ kind: z.literal("languages"), languages: z.array(Lang).min(1) }),
  z.object({ kind: z.literal("unknown") }),
]);
export type Subtitles = z.infer<typeof Subtitles>;

export const ScreeningTag = z.enum([
  "premiere",
  "preview",
  "last-screening",
  "event-cinema",
  "senior",
  "kids",
  "baby",
  "discount",
  "no-dialogue",
  "accessible",
]);
export type ScreeningTag = z.infer<typeof ScreeningTag>;

export const Availability = z.enum([
  "available",
  "few-left",
  "sold-out",
  "not-bookable",
  "unknown",
]);
export type Availability = z.infer<typeof Availability>;

export const Screening = z.object({
  id: Id,
  provider: ProviderId,
  sourceId: z.string(),
  venueId: Id,
  auditoriumId: Id.optional(),
  listingId: Id,
  filmId: z.string().optional(),

  startsAt: OffsetDateTime,
  endsAt: OffsetDateTime.optional(),
  /** Cinema's business day; a show after midnight may belong to the previous day. */
  businessDate: IsoDate,

  presentation: z.object({
    projection: z.enum(["digital", "35mm", "70mm", "16mm"]),
    dimension: z.enum(["2d", "3d"]),
    formats: z.array(Feature),
  }),
  /** Spoken languages. Empty = unknown. */
  audio: z.array(Lang),
  /** True for a dubbed version, false for original language, absent if unknown. */
  dubbed: z.boolean().optional(),
  subtitles: Subtitles,

  ageLimit: FinnishRating.optional(),
  ageRecommendation: z.number().int().positive().optional(),
  /** Alcohol served. Absent = unknown. */
  licensed: z.boolean().optional(),
  tags: z.array(ScreeningTag),
  series: z.array(z.string()),

  availability: Availability,
  price: z
    .object({
      amountCents: z.number().int().nonnegative(),
      currency: z.literal("EUR"),
      note: z.string().optional(),
    })
    .optional(),
  ticketUrl: z.url().optional(),

  /** Upstream labels the parser does not understand yet. */
  unmappedLabels: z.array(z.string()),
  fetchedAt: z.iso.datetime(),
});
export type Screening = z.infer<typeof Screening>;

export const Warning = z.object({
  code: z.string(),
  message: z.string(),
  context: z.record(z.string(), z.unknown()).optional(),
});
export type Warning = z.infer<typeof Warning>;

/** Everything one adapter run produces. */
export const ProviderBatch = z.object({
  provider: Provider,
  fetchedAt: z.iso.datetime(),
  venues: z.array(Venue),
  auditoriums: z.array(Auditorium),
  listings: z.array(FilmListing),
  screenings: z.array(Screening),
  warnings: z.array(Warning),
});
export type ProviderBatch = z.infer<typeof ProviderBatch>;
