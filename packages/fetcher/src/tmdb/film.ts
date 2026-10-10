import { FinnishRating, type Film, type Lang, type Localized, type Rating } from "@pgtm/model";
import type { MovieDetails } from "./raw.ts";

export const imageUrl = (path: string, size: "w185" | "w342" | "w500" | "w780" | "original") =>
  `https://image.tmdb.org/t/p/${size}${path}`;

const LANGS = ["fi", "sv", "en"] as const;

const localized = (details: MovieDetails, field: "title" | "overview"): Localized => {
  const out: Localized = {};
  for (const lang of LANGS) {
    // Prefer the translation for the language's home country (fi-FI, sv-SE, en-US).
    const candidates = details.translations.translations.filter((t) => t.iso_639_1 === lang);
    const home = { fi: "FI", sv: "SE", en: "US" }[lang];
    const text = (
      candidates.find((t) => t.iso_3166_1 === home)?.data[field] ??
      candidates.find((t) => t.data[field])?.data[field]
    )?.trim();
    if (text) out[lang] = text;
  }
  // An empty translated title means "same as the original".
  if (field === "title" && details.original_language) {
    const lang = details.original_language as (typeof LANGS)[number];
    if (LANGS.includes(lang) && !out[lang]) out[lang] = details.original_title;
  }
  return out;
};

const finnishRelease = (details: MovieDetails) => {
  const fi = details.release_dates.results.find((r) => r.iso_3166_1 === "FI");
  const dates = [...(fi?.release_dates ?? [])].sort((a, b) =>
    a.release_date.localeCompare(b.release_date),
  );
  const certification = dates.map((d) => d.certification?.trim()).find(Boolean);
  const rating = FinnishRating.safeParse(certification);
  const theatrical = dates.find((d) => d.type === 3 || d.type === 2);
  return {
    ...(rating.success && { rating: rating.data }),
    ...(theatrical && { finnishReleaseDate: theatrical.release_date.slice(0, 10) }),
  };
};

/** Finnish poster first, then English, then a textless one; best voted within each. */
const pickPoster = (details: MovieDetails): string | undefined => {
  for (const lang of ["fi", "en", null]) {
    const best = details.images.posters
      .filter((p) => p.iso_639_1 === lang)
      .sort((a, b) => (b.vote_average ?? 0) - (a.vote_average ?? 0))[0];
    if (best) return best.file_path;
  }
  return details.poster_path ?? undefined;
};

const trailers = (details: MovieDetails): Film["trailers"] =>
  details.videos.results
    .filter((v) => v.site === "YouTube" && v.type === "Trailer")
    .sort((a, b) => Number(b.official ?? false) - Number(a.official ?? false))
    .map((v) => ({
      site: "YouTube" as const,
      key: v.key,
      name: v.name,
      ...(v.iso_639_1 && /^[a-z]{2}$/.test(v.iso_639_1) && { language: v.iso_639_1 as Lang }),
    }));

/** Below this many votes a TMDB score is noise (a handful of early viewers). */
export const MIN_TMDB_VOTES = 20;

/** TMDB's own user score as a rating, when enough people voted. */
export const tmdbRating = (details: MovieDetails): Rating[] => {
  const average = details.vote_average;
  const votes = details.vote_count ?? 0;
  if (average === null || average === undefined || votes < MIN_TMDB_VOTES) return [];
  return [
    { source: "tmdb", score: Math.round(average * 10), display: `${average.toFixed(1)}/10`, votes },
  ];
};

/** Pure: TMDB details -> Film. */
export const toFilm = (details: MovieDetails, fetchedAt: string): Film => {
  const posterPath = pickPoster(details);
  const lang = details.original_language;
  return {
    id: `tmdb:${details.id}`,
    tmdbId: details.id,
    ...(details.imdb_id && { imdbId: details.imdb_id }),
    title: localized(details, "title"),
    originalTitle: details.original_title,
    ...(lang && /^[a-z]{2}$/.test(lang) && { originalLanguage: lang }),
    ...(details.release_date && { releaseDate: details.release_date }),
    ...finnishRelease(details),
    ...(details.runtime && details.runtime > 0 && { runtimeMinutes: details.runtime }),
    genres: details.genres.map((g) => g.name),
    countries: details.production_countries.map((c) => c.iso_3166_1),
    overview: localized(details, "overview"),
    ...(posterPath && { posterPath }),
    ...(details.backdrop_path && { backdropPath: details.backdrop_path }),
    trailers: trailers(details),
    ratings: tmdbRating(details),
    fetchedAt,
  };
};
