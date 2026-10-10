import { describe, expect, it } from "vitest";
import { formatFilm, formatScreenings, languageLabel, table } from "../src/search/format.ts";
import type { FilmDetails, ShowtimeRow } from "../src/search/showtimes.ts";

const row = (overrides: Partial<ShowtimeRow> = {}): ShowtimeRow => ({
  startsAt: new Date("2026-10-10T17:00:00.000Z"),
  film: "The Odyssey",
  city: "Helsinki",
  venue: "Tennispalatsi Helsinki",
  screen: "LUXE 8",
  audio: ["en"],
  subtitlesKind: "languages",
  subtitlesLanguages: ["fi", "sv"],
  formats: ["luxe"],
  licensed: true,
  ageLimit: null,
  availability: "available",
  ticketUrl: "https://tickets.example/1",
  distanceKm: null,
  rottenTomatoes: null,
  imdb: null,
  ...overrides,
});

describe("languageLabel", () => {
  it.each([
    [row(), "EN, subs FI/SV"],
    [row({ audio: ["fi"], subtitlesKind: "none", subtitlesLanguages: [] }), "FI"],
    [row({ audio: ["ko", "ja"] }), "KO+JA, subs FI/SV"],
    [row({ audio: [], subtitlesKind: "unknown", subtitlesLanguages: [] }), "?"],
  ])("%#", (input, expected) => {
    expect(languageLabel(input)).toBe(expected);
  });
});

it("aligns table columns", () => {
  expect(table(["A", "Long"], [["xx", "y"]])).toBe("A   Long\n--  ----\nxx  y");
});

it("formats screenings in Helsinki time with extras", () => {
  const text = formatScreenings([row({ ageLimit: "K-18", availability: "sold-out" })], false);
  expect(text).toContain("20.00");
  expect(text).toContain("LUXE bar K-18 sold-out");
  expect(text).not.toContain("tickets.example");
  expect(formatScreenings([row()], true)).toContain("https://tickets.example/1");
  expect(formatScreenings([], false)).toBe("  No screenings found.");
});

it("adds a film column for the all-films listing", () => {
  const text = formatScreenings([row()], false, { withFilm: true });
  expect(text.split("\n")[0]).toMatch(/Venue\s+Film\s+Screen/);
  expect(text).toContain("The Odyssey");
  expect(formatScreenings([row()], false)).not.toContain("Film");
});

it("adds a distance column when screenings were searched near a point", () => {
  const text = formatScreenings([row({ distanceKm: 3.46 }), row({ distanceKm: 12.04 })], false);
  expect(text.split("\n")[0]).toMatch(/Time\s+Km\s+City/);
  expect(text).toContain("3.5");
  expect(text).toContain("12");
  expect(formatScreenings([row()], false)).not.toContain("Km");
});

it("formats a film heading with the cinemas' title and the original", () => {
  const film = {
    id: "tmdb:2",
    tmdbId: 2,
    imdbId: "tt1",
    titleFi: null,
    titleSv: null,
    titleEn: "PAW Patrol: The Dino Movie",
    localTitle: "Ryhmä Hau: Dinoelokuva",
    originalTitle: "PAW Patrol: The Dino Movie",
    releaseDate: "2026-07-23",
    finnishReleaseDate: "2026-08-07",
    runtimeMinutes: 88,
    rating: "K-7",
    genres: ["Animaatio"],
    countries: ["CA", "US"],
    overviewFi: null,
    overviewSv: null,
    overviewEn: "Pups and dinosaurs.",
    posterPath: "/p.jpg",
    ratings: [
      { source: "rotten-tomatoes", score: 86, display: "86%", votes: null },
      { source: "imdb", score: 61, display: "6.1/10", votes: 1_497_908 },
      { source: "tmdb", score: 70, display: "7.0/10", votes: 412 },
    ],
  } as FilmDetails;
  const text = formatFilm(film, 1);
  expect(text.split("\n")[0]).toBe(
    "Ryhmä Hau: Dinoelokuva (PAW Patrol: The Dino Movie)  [match 1.00]",
  );
  expect(text).toContain("2026 · 88 min · K-7 · Animaatio · CA, US");
  expect(text).toContain("https://image.tmdb.org/t/p/w500/p.jpg");
  // Ratings are opt-in.
  expect(text).not.toContain("RT 86%");
  expect(formatFilm(film, 1, { withRatings: true })).toContain(
    "RT 86% · IMDb 6.1 (1.5M) · TMDB 7.0",
  );
});

it("adds rating columns to the all-films listing", () => {
  const rows = [row({ rottenTomatoes: 93, imdb: 79 }), row()];
  expect(formatScreenings(rows, false, { withFilm: true })).not.toContain("93%");
  const text = formatScreenings(rows, false, { withFilm: true, withRatings: true });
  expect(text.split("\n")[0]).toMatch(/Film\s+RT\s+IMDb\s+Screen/);
  expect(text).toContain("93%");
  expect(text).toContain("7.9");
});
