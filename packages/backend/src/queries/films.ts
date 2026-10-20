import type { z } from "@hono/zod-openapi";
import { sql, type Kysely } from "kysely";
import type { Film, FilmOpening, FilmSummary, SearchHit } from "../api/schemas.ts";
import type { DB } from "../db/types.ts";
import { filmDetails, listingDetails, searchFilms } from "../search/showtimes.ts";
import { backdropUrl, posterUrl, yearOf } from "./common.ts";

type FilmOut = z.infer<typeof Film>;

const trailersOf = (value: unknown): FilmOut["trailers"] =>
  Array.isArray(value)
    ? value.flatMap((t) =>
        t && typeof t === "object" && "site" in t && "key" in t
          ? [
              {
                site: String(t.site),
                key: String(t.key),
                name: String(("name" in t && t.name) || ""),
              },
            ]
          : [],
      )
    : [];

/** A TMDB film (`tmdb:…`) or an unmatched cinema listing, with everything we know. */
export const getFilm = async (db: Kysely<DB>, id: string): Promise<FilmOut | undefined> => {
  const film = await filmDetails(db, id);
  if (film) {
    return {
      id: film.id,
      kind: "film",
      isEvent: false,
      title: film.titleFi ?? film.localTitle ?? film.titleEn ?? film.originalTitle,
      originalTitle: film.originalTitle,
      year: yearOf(film.releaseDate),
      runtimeMinutes: film.runtimeMinutes,
      rating: film.rating,
      posterUrl: posterUrl(film.posterPath),
      ratings: film.ratings,
      tmdbId: film.tmdbId,
      imdbId: film.imdbId,
      titles: { fi: film.titleFi ?? film.localTitle, sv: film.titleSv, en: film.titleEn },
      releaseDate: film.releaseDate,
      finnishReleaseDate: film.finnishReleaseDate,
      genres: film.genres,
      countries: film.countries,
      overview: { fi: film.overviewFi, sv: film.overviewSv, en: film.overviewEn },
      backdropUrl: backdropUrl(film.backdropPath),
      trailers: trailersOf(film.trailers),
    };
  }
  const listing = await listingDetails(db, id);
  if (!listing) {
    return undefined;
  }
  return {
    id: listing.id,
    kind: "listing",
    isEvent: listing.kind === "event",
    title:
      listing.titleFi ?? listing.titleSv ?? listing.titleEn ?? listing.originalTitle ?? listing.id,
    originalTitle: listing.originalTitle,
    year: listing.year,
    runtimeMinutes: listing.runtimeMinutes,
    rating: listing.rating,
    posterUrl: null,
    ratings: [],
    tmdbId: null,
    imdbId: null,
    titles: { fi: listing.titleFi, sv: listing.titleSv, en: listing.titleEn },
    releaseDate: null,
    finnishReleaseDate: null,
    genres: listing.genres,
    countries: listing.countries,
    overview: { fi: null, sv: null, en: null },
    backdropUrl: null,
    trailers: [],
  };
};

const summaryOf = (film: FilmOut): z.infer<typeof FilmSummary> => ({
  id: film.id,
  kind: film.kind,
  isEvent: film.isEvent,
  title: film.title,
  originalTitle: film.originalTitle,
  year: film.year,
  runtimeMinutes: film.runtimeMinutes,
  rating: film.rating,
  posterUrl: film.posterUrl,
  ratings: film.ratings,
});

/** Fuzzy title search (any language, typos allowed), best first. */
export const searchFilmSummaries = async (
  db: Kysely<DB>,
  term: string,
  limit: number,
): Promise<z.infer<typeof SearchHit>[]> => {
  const hits = await searchFilms(db, term, { limit });
  const films = await Promise.all(hits.map((h) => getFilm(db, h.id)));
  return hits.flatMap((hit, i) => {
    const film = films[i];
    return film ? [{ score: Number(hit.score.toFixed(3)), film: summaryOf(film) }] : [];
  });
};

/**
 * TMDB films whose first screening (the earliest programme day of any screening not
 * removed, previews included) falls between `from` and `to`, earliest first. Our history
 * starts on 2026-10-09: a film running before that "first shows" on its first day with us.
 */
export const filmOpenings = async (
  db: Kysely<DB>,
  from: string,
  to: string,
  /** Only films with a screening (not removed) between these days too. */
  playing?: { from: string; to: string },
): Promise<z.infer<typeof FilmOpening>[]> => {
  let query = db
    .selectFrom("screenings")
    .select(["filmId", sql<string>`min(business_date)::text`.as("firstShowing")])
    .where("filmId", "is not", null)
    .where("removedAt", "is", null)
    .groupBy("filmId")
    .having(sql<boolean>`min(business_date) between ${from}::date and ${to}::date`);
  if (playing) {
    query = query.having(
      sql<boolean>`bool_or(business_date between ${playing.from}::date and ${playing.to}::date)`,
    );
  }
  const rows = await query.orderBy("firstShowing").execute();
  const films = await Promise.all(rows.map((r) => getFilm(db, r.filmId!)));
  return rows.flatMap((row, i) => {
    const film = films[i];
    return film ? [{ film: summaryOf(film), firstShowing: row.firstShowing }] : [];
  });
};
