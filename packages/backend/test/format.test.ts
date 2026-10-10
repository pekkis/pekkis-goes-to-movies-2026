import { describe, expect, it } from "vitest";
import { formatFilm, formatScreenings, languageLabel, table } from "../src/search/format.ts";
import type { FilmDetails, ShowtimeRow } from "../src/search/showtimes.ts";

const row = (overrides: Partial<ShowtimeRow> = {}): ShowtimeRow => ({
  startsAt: new Date("2026-10-10T17:00:00.000Z"),
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
  expect(formatScreenings([], false)).toBe("  No screenings on this date.");
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
  } as FilmDetails;
  const text = formatFilm(film, 1);
  expect(text.split("\n")[0]).toBe(
    "Ryhmä Hau: Dinoelokuva (PAW Patrol: The Dino Movie)  [match 1.00]",
  );
  expect(text).toContain("2026 · 88 min · K-7 · Animaatio · CA, US");
  expect(text).toContain("https://image.tmdb.org/t/p/w500/p.jpg");
});
