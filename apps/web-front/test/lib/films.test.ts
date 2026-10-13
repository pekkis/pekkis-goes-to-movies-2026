import { describe, expect, it } from "vitest";
import { byTitle, groupByFilm } from "../../src/lib/films.ts";
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
