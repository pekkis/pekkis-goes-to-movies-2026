import type { MovieDetails } from "../../src/tmdb/raw.ts";

/** Minimal TMDB movie details for tests; override what the test is about. */
export const details = (
  overrides: Partial<MovieDetails> & { id: number; title: string },
): MovieDetails => ({
  original_title: overrides.title,
  original_language: "en",
  release_date: "2026-09-01",
  runtime: 100,
  genres: [],
  production_countries: [{ iso_3166_1: "US" }],
  translations: { translations: [] },
  alternative_titles: { titles: [] },
  release_dates: { results: [] },
  videos: { results: [] },
  images: { posters: [] },
  ...overrides,
});
