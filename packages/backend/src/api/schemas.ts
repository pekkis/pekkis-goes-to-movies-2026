import { z } from "@hono/zod-openapi";

/**
 * The API's public response shapes. They are the contract with clients (Flutter, React):
 * change them deliberately, never by returning database rows directly.
 * Unknown values are `null`; timestamps are Helsinki local time with offset.
 */

const nullableString = z.string().nullable();

export const Geo = z
  .object({ lat: z.number(), lon: z.number() })
  .openapi("Geo", { example: { lat: 62.236603, lon: 25.734976 } });

export const Provider = z
  .object({
    id: z.string().openapi({ example: "kinoaurora" }),
    name: z.string(),
    homepage: z.string(),
    /** buy | reserve | door | info */
    booking: z.string(),
  })
  .openapi("Provider");

export const Venue = z
  .object({
    id: z.string().openapi({ example: "kinoaurora:venue:jyvaskyla" }),
    name: z.string(),
    shortName: nullableString,
    city: z.string(),
    address: nullableString,
    postalCode: nullableString,
    geo: Geo.nullable(),
    url: nullableString,
    provider: Provider,
  })
  .openapi("Venue");

export const VenueRef = z
  .object({ id: z.string(), name: z.string(), city: z.string(), geo: Geo.nullable() })
  .openapi("VenueRef");

export const FilmSummary = z
  .object({
    /** `tmdb:…` for a film matched to TMDB, otherwise the cinema's listing id. */
    id: z.string().openapi({ example: "tmdb:1185806" }),
    /** `film`: matched to TMDB (posters, synopsis). `listing`: only what the cinema says. */
    kind: z.enum(["film", "listing"]),
    /** Opera, concert or other event cinema. */
    isEvent: z.boolean(),
    title: z.string(),
    originalTitle: nullableString,
    year: z.number().int().nullable(),
    runtimeMinutes: z.number().int().nullable(),
    rating: nullableString.openapi({ example: "K-12" }),
    posterUrl: nullableString,
  })
  .openapi("FilmSummary");

export const Screening = z
  .object({
    id: z.string().openapi({ example: "finnkino:show:12345" }),
    startsAt: z.string().openapi({ example: "2026-10-10T18:00:00+03:00" }),
    endsAt: nullableString,
    /** The cinema's programme day; shows after midnight belong to the previous one. */
    businessDate: z.string().openapi({ example: "2026-10-10" }),
    venue: VenueRef,
    auditorium: nullableString,
    film: FilmSummary,
    projection: z.string(),
    dimension: z.string(),
    formats: z.array(z.string()),
    /** ISO 639-1 codes; empty when unknown. */
    audio: z.array(z.string()),
    dubbed: z.boolean().nullable(),
    subtitles: z.object({
      /** languages | none | unknown */
      kind: z.string(),
      languages: z.array(z.string()),
    }),
    tags: z.array(z.string()),
    series: z.array(z.string()),
    ageLimit: nullableString,
    /** available | few-left | sold-out | not-bookable | unknown */
    availability: z.string(),
    price: z
      .object({ amountCents: z.number().int(), currency: z.string(), note: nullableString })
      .nullable(),
    /** Always the cinema's own page: we never sell tickets. */
    ticketUrl: nullableString,
  })
  .openapi("Screening");

export const ScreeningPage = z
  .object({
    date: z.string(),
    items: z.array(Screening),
    /** Pass as `cursor` for the next page; null on the last page. */
    nextCursor: nullableString,
  })
  .openapi("ScreeningPage");

export const Film = FilmSummary.extend({
  tmdbId: z.number().int().nullable(),
  imdbId: nullableString,
  titles: z.object({ fi: nullableString, sv: nullableString, en: nullableString }),
  releaseDate: nullableString,
  finnishReleaseDate: nullableString,
  genres: z.array(z.string()),
  countries: z.array(z.string()),
  overview: z.object({ fi: nullableString, sv: nullableString, en: nullableString }),
  backdropUrl: nullableString,
  trailers: z.array(z.object({ site: z.string(), key: z.string(), name: z.string() })),
}).openapi("Film");

export const SearchHit = z
  .object({ score: z.number().openapi({ example: 0.83 }), film: FilmSummary })
  .openapi("SearchHit");

export const Health = z.object({ ok: z.boolean(), db: z.boolean() }).openapi("Health");

export const ErrorBody = z
  .object({ error: z.string(), issues: z.array(z.unknown()).optional() })
  .openapi("Error");
