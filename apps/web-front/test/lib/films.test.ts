import { describe, expect, it } from "vitest";
import { byTitle, filmIdOfSlug, filmPath, groupByFilm } from "../../src/lib/films.ts";
import { screening } from "../fixtures.ts";

const film = (id: string, title: string) => ({ ...screening().film, id, title });

describe("groupByFilm", () => {
  it("lists each film once, alphabetically, with its shows in time order", () => {
    const groups = groupByFilm([
      screening({ id: "a", startsAt: "2026-10-13T20:00:00+03:00", film: film("tmdb:1", "Tony") }),
      screening({ id: "b", startsAt: "2026-10-13T12:00:00+03:00", film: film("tmdb:2", "Ötökät") }),
      screening({ id: "c", startsAt: "2026-10-13T13:00:00+03:00", film: film("tmdb:1", "Tony") }),
      screening({
        id: "d",
        startsAt: "2026-10-13T21:00:00+03:00",
        film: film("tmdb:3", "Kerro kaikille"),
      }),
    ]);
    expect(groups.map((g) => g.film.title)).toEqual(["Kerro kaikille", "Tony", "Ötökät"]);
    expect(groups[1]?.screenings.map((s) => s.id)).toEqual(["c", "a"]);
  });
});

describe("byTitle", () => {
  it.each([
    [
      ["Zorro", "Ötökät", "Äiti", "Åke"],
      ["Zorro", "Åke", "Äiti", "Ötökät"],
    ],
    [
      ["avatar", "Batman", "Avengers"],
      ["avatar", "Avengers", "Batman"],
    ],
    [
      ["Rocky 10", "Rocky 2"],
      ["Rocky 2", "Rocky 10"],
    ],
  ])("sorts %j as %j", (titles, expected) => {
    expect(
      titles
        .map((title) => ({ title }))
        .toSorted(byTitle)
        .map((f) => f.title),
    ).toEqual(expected);
  });
});

describe("film pages", () => {
  it.each([
    [{ id: "tmdb:1450460", title: "Lapin sota" }, "/fi/elokuvat/lapin-sota-1450460"],
    [{ id: "tmdb:957", title: "Avaruusboltsit" }, "/fi/elokuvat/avaruusboltsit-957"],
    [{ id: "tmdb:7", title: "!!!" }, "/fi/elokuvat/7"],
    [{ id: "biorex:film:1518", title: "Ryhmä Hau" }, undefined],
  ])("filmPath(%o) = %s", (named, path) => {
    expect(filmPath(named)).toBe(path);
  });

  it.each([
    ["lapin-sota-1450460", "tmdb:1450460"],
    ["7", "tmdb:7"],
    ["blade-runner-2049-335984", "tmdb:335984"],
    ["lapin-sota", undefined],
  ])("filmIdOfSlug(%s) = %s", (slug, id) => {
    expect(filmIdOfSlug(slug)).toBe(id);
  });
});
