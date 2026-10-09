import { describe, expect, it } from "vitest";
import { Film } from "../../src/model/schema.ts";
import { imageUrl, toFilm } from "../../src/tmdb/film.ts";
import { MovieDetails } from "../../src/tmdb/raw.ts";
import { loadFixture } from "../fixtures.ts";
import { details } from "./factory.ts";

const FETCHED = "2026-10-09T12:00:00.000Z";

describe("toFilm", () => {
  const film = toFilm(MovieDetails.parse(loadFixture("tmdb", "movie-1185806.json")), FETCHED);

  it("produces a valid Film", () => {
    expect(() => Film.parse(film)).not.toThrow();
  });

  it("maps a real TMDB record", () => {
    expect(film).toMatchObject({
      id: "tmdb:1185806",
      tmdbId: 1185806,
      imdbId: "tt29356163",
      originalTitle: "PAW Patrol: The Dino Movie",
      originalLanguage: "en",
      title: { sv: "Paw Patrol: Dinosaurie-filmen", en: "PAW Patrol: The Dino Movie" },
      releaseDate: "2026-07-23",
      finnishReleaseDate: "2026-08-07",
      runtimeMinutes: 88,
      rating: "K-7",
      genres: ["Animaatio", "Seikkailu", "Perhe", "Fantasia", "Komedia"],
      countries: ["CA", "US"],
      backdropPath: "/6TSxLmwT7j1ugtKi8NyMmdzWAGj.jpg",
      trailers: [{ site: "YouTube", key: "xgI5iYmOf5Q", name: "Official Trailer", language: "en" }],
      fetchedAt: FETCHED,
    });
    expect(film.overview.en).toMatch(/^The Paw Patrol lands/);
  });

  it("uses the best-voted English poster when there is no Finnish one", () => {
    expect(film.posterPath).toBe("/qnin56Syy5rbG7KCaxWY7SPuy6p.jpg");
  });
});

describe("toFilm details", () => {
  const poster = (lang: string | null, path: string, vote = 5) => ({
    iso_639_1: lang,
    file_path: path,
    vote_average: vote,
  });

  it("prefers a Finnish poster", () => {
    const film = toFilm(
      details({
        id: 1,
        title: "X",
        images: { posters: [poster("en", "/en.jpg", 9), poster("fi", "/fi.jpg", 1)] },
      }),
      FETCHED,
    );
    expect(film.posterPath).toBe("/fi.jpg");
  });

  it("fills the original-language title when the translation leaves it empty", () => {
    const film = toFilm(
      details({
        id: 1,
        title: "Kerro kaikille",
        original_language: "fi",
        translations: {
          translations: [
            { iso_639_1: "fi", iso_3166_1: "FI", data: { title: "", overview: "Juoni." } },
          ],
        },
      }),
      FETCHED,
    );
    expect(film.title.fi).toBe("Kerro kaikille");
    expect(film.overview.fi).toBe("Juoni.");
  });

  it("ignores a certification that is not a Finnish rating", () => {
    const film = toFilm(
      details({
        id: 1,
        title: "X",
        release_dates: {
          results: [
            {
              iso_3166_1: "FI",
              release_dates: [
                { certification: "PG-13", release_date: "2026-01-01T00:00:00.000Z", type: 3 },
              ],
            },
          ],
        },
      }),
      FETCHED,
    );
    expect(film).not.toHaveProperty("rating");
    expect(film.finnishReleaseDate).toBe("2026-01-01");
  });
});

it("builds image URLs", () => {
  expect(imageUrl("/a.jpg", "w500")).toBe("https://image.tmdb.org/t/p/w500/a.jpg");
});
