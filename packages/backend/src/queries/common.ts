import type { z } from "@hono/zod-openapi";
import type { FilmSummary } from "../api/schemas.ts";

/** A map viewport, WGS 84. */
export type Bbox = { minLon: number; minLat: number; maxLon: number; maxLat: number };

const TMDB_IMAGES = "https://image.tmdb.org/t/p";
export const posterUrl = (path: string | null): string | null =>
  path ? `${TMDB_IMAGES}/w500${path}` : null;
export const backdropUrl = (path: string | null): string | null =>
  path ? `${TMDB_IMAGES}/w1280${path}` : null;

export const geoOf = (lat: number | null, lon: number | null) =>
  lat !== null && lon !== null ? { lat, lon } : null;

export const yearOf = (date: string | null): number | null =>
  date ? Number(date.slice(0, 4)) : null;

/** Columns both sides of a screening's film need; `f` is null when not matched to TMDB. */
export type FilmColumns = {
  filmId: string | null;
  listingId: string;
  listingKind: string;
  listingTitleFi: string | null;
  listingTitleEn: string | null;
  listingOriginalTitle: string | null;
  listingYear: number | null;
  listingRuntime: number | null;
  listingRating: string | null;
  filmTitleFi: string | null;
  filmTitleEn: string | null;
  filmOriginalTitle: string | null;
  filmReleaseDate: string | null;
  filmRuntime: number | null;
  filmRating: string | null;
  filmPosterPath: string | null;
};

/**
 * One summary for matched and unmatched films. A TMDB film without a Finnish title uses
 * the title the cinema lists it under (e.g. "Ryhmä Hau: Dinoelokuva").
 */
export const toFilmSummary = (r: FilmColumns): z.infer<typeof FilmSummary> =>
  r.filmId
    ? {
        id: r.filmId,
        kind: "film",
        isEvent: r.listingKind === "event",
        title:
          r.filmTitleFi ?? r.listingTitleFi ?? r.filmTitleEn ?? r.filmOriginalTitle ?? r.filmId,
        originalTitle: r.filmOriginalTitle,
        year: yearOf(r.filmReleaseDate),
        runtimeMinutes: r.filmRuntime ?? r.listingRuntime,
        rating: r.filmRating ?? r.listingRating,
        posterUrl: posterUrl(r.filmPosterPath),
      }
    : {
        id: r.listingId,
        kind: "listing",
        isEvent: r.listingKind === "event",
        title: r.listingTitleFi ?? r.listingTitleEn ?? r.listingOriginalTitle ?? r.listingId,
        originalTitle: r.listingOriginalTitle,
        year: r.listingYear,
        runtimeMinutes: r.listingRuntime,
        rating: r.listingRating,
        posterUrl: null,
      };
