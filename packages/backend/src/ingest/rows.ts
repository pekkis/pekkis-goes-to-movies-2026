import type { Auditorium, Film, FilmListing, Provider, Screening, Venue } from "@pgtm/model";
import type { Insertable } from "kysely";
import type { DB } from "../db/types.ts";

/**
 * Pure mapping from the model to table rows. "Unknown" (an absent optional field in the
 * model) becomes NULL. History columns (first/last seen, removed) are set by the upsert.
 */

export type ProviderRow = Insertable<DB["providers"]>;
export type VenueRow = Insertable<DB["venues"]>;
export type AuditoriumRow = Insertable<DB["auditoriums"]>;
export type FilmRow = Insertable<DB["films"]>;
export type FilmListingRow = Insertable<DB["filmListings"]>;
export type FilmRatingRow = Omit<Insertable<DB["filmRatings"]>, "createdAt" | "updatedAt">;
export type ScreeningRow = Omit<
  Insertable<DB["screenings"]>,
  "firstSeenAt" | "lastSeenAt" | "removedAt" | "createdAt" | "updatedAt"
>;

export const providerRow = (p: Provider): ProviderRow => ({
  id: p.id,
  name: p.name,
  homepage: p.homepage,
  platform: p.platform,
  booking: p.booking,
});

export const venueRow = (v: Venue): VenueRow => ({
  id: v.id,
  providerId: v.provider,
  sourceId: v.sourceId,
  name: v.name,
  shortName: v.shortName ?? null,
  city: v.city,
  address: v.address ?? null,
  postalCode: v.postalCode ?? null,
  lat: v.geo?.lat ?? null,
  lon: v.geo?.lon ?? null,
  url: v.url ?? null,
});

export const auditoriumRow = (a: Auditorium): AuditoriumRow => ({
  id: a.id,
  venueId: a.venueId,
  name: a.name,
  seats: a.seats ?? null,
  features: a.features,
  ageLimit: a.ageLimit ?? null,
});

export const filmRow = (f: Film): FilmRow => ({
  id: f.id,
  tmdbId: f.tmdbId,
  imdbId: f.imdbId ?? null,
  titleFi: f.title.fi ?? null,
  titleSv: f.title.sv ?? null,
  titleEn: f.title.en ?? null,
  originalTitle: f.originalTitle,
  originalLanguage: f.originalLanguage ?? null,
  releaseDate: f.releaseDate ?? null,
  finnishReleaseDate: f.finnishReleaseDate ?? null,
  runtimeMinutes: f.runtimeMinutes ?? null,
  rating: f.rating ?? null,
  genres: f.genres,
  countries: f.countries,
  overviewFi: f.overview.fi ?? null,
  overviewSv: f.overview.sv ?? null,
  overviewEn: f.overview.en ?? null,
  posterPath: f.posterPath ?? null,
  backdropPath: f.backdropPath ?? null,
  trailers: JSON.stringify(f.trailers),
  fetchedAt: f.fetchedAt,
});

export const filmRatingRows = (f: Film): FilmRatingRow[] =>
  f.ratings.map((r) => ({
    filmId: f.id,
    source: r.source,
    score: r.score,
    display: r.display,
    votes: r.votes ?? null,
    fetchedAt: f.fetchedAt,
  }));

export const filmListingRow = (l: FilmListing): FilmListingRow => ({
  id: l.id,
  providerId: l.provider,
  sourceId: l.sourceId,
  titleFi: l.title.fi ?? null,
  titleSv: l.title.sv ?? null,
  titleEn: l.title.en ?? null,
  originalTitle: l.originalTitle ?? null,
  year: l.year ?? null,
  runtimeMinutes: l.runtimeMinutes ?? null,
  rating: l.rating ?? null,
  genres: l.genres,
  countries: l.countries,
  kind: l.kind,
  filmId: l.filmId ?? null,
  match: l.match ?? null,
});

export const screeningRow = (s: Screening): ScreeningRow => ({
  id: s.id,
  providerId: s.provider,
  sourceId: s.sourceId,
  venueId: s.venueId,
  auditoriumId: s.auditoriumId ?? null,
  listingId: s.listingId,
  filmId: s.filmId ?? null,
  startsAt: s.startsAt,
  endsAt: s.endsAt ?? null,
  businessDate: s.businessDate,
  projection: s.presentation.projection,
  dimension: s.presentation.dimension,
  formats: s.presentation.formats,
  audio: s.audio,
  dubbed: s.dubbed ?? null,
  subtitlesKind: s.subtitles.kind,
  subtitlesLanguages: s.subtitles.kind === "languages" ? s.subtitles.languages : [],
  ageLimit: s.ageLimit ?? null,
  ageRecommendation: s.ageRecommendation ?? null,
  licensed: s.licensed ?? null,
  tags: s.tags,
  series: s.series,
  availability: s.availability,
  priceAmountCents: s.price?.amountCents ?? null,
  priceCurrency: s.price?.currency ?? null,
  priceNote: s.price?.note ?? null,
  ticketUrl: s.ticketUrl ?? null,
  unmappedLabels: s.unmappedLabels,
  fetchedAt: s.fetchedAt,
});
