import type { Film, FilmCatalog, ProviderBatch, Screening } from "@pgtm/model";

/** Small, valid model objects for tests; override what a test is about. */

export const FETCHED_AT = "2026-10-09T12:00:00.000Z";

export const screening = (sourceId: string, overrides: Partial<Screening> = {}): Screening => ({
  id: `testchain:show:${sourceId}`,
  provider: "testchain",
  sourceId,
  venueId: "testchain:venue:1",
  auditoriumId: "testchain:screen:1",
  listingId: "testchain:film:10",
  filmId: "tmdb:100",
  startsAt: "2026-10-10T18:00:00+03:00",
  endsAt: "2026-10-10T20:00:00+03:00",
  businessDate: "2026-10-10",
  presentation: { projection: "digital", dimension: "2d", formats: ["imax"] },
  audio: ["en"],
  dubbed: false,
  subtitles: { kind: "languages", languages: ["fi", "sv"] },
  tags: [],
  series: [],
  availability: "available",
  ticketUrl: `https://tickets.example/${sourceId}`,
  unmappedLabels: [],
  fetchedAt: FETCHED_AT,
  ...overrides,
});

export const film = (overrides: Partial<Film> = {}): Film => ({
  id: "tmdb:100",
  tmdbId: 100,
  title: { fi: "Testielokuva", en: "Test Film" },
  originalTitle: "Test Film",
  originalLanguage: "en",
  releaseDate: "2026-09-01",
  runtimeMinutes: 120,
  rating: "K-12",
  genres: ["Draama"],
  countries: ["FI"],
  overview: { en: "A film for tests." },
  posterPath: "/poster.jpg",
  trailers: [{ site: "YouTube", key: "abc", name: "Trailer" }],
  fetchedAt: FETCHED_AT,
  ...overrides,
});

export const catalog = (films: Film[] = [film()]): FilmCatalog => ({
  generatedAt: FETCHED_AT,
  films,
  unmatched: [],
});

export const batch = (
  screenings: Screening[],
  overrides: Partial<ProviderBatch> = {},
): ProviderBatch => ({
  provider: {
    id: "testchain",
    name: "Test Chain",
    homepage: "https://example.com",
    platform: "custom",
    booking: "buy",
  },
  fetchedAt: FETCHED_AT,
  window: { from: "2026-10-09", to: "2026-10-15" },
  venues: [
    {
      id: "testchain:venue:1",
      provider: "testchain",
      sourceId: "1",
      name: "Testikino",
      city: "Jyväskylä",
      geo: { lat: 62.24, lon: 25.75 },
    },
  ],
  auditoriums: [
    { id: "testchain:screen:1", venueId: "testchain:venue:1", name: "Sali 1", features: ["imax"] },
  ],
  listings: [
    {
      id: "testchain:film:10",
      provider: "testchain",
      sourceId: "10",
      title: { fi: "Testielokuva" },
      runtimeMinutes: 120,
      genres: [],
      countries: [],
      kind: "film",
      filmId: "tmdb:100",
      match: "auto",
    },
  ],
  screenings,
  warnings: [],
  ...overrides,
});
