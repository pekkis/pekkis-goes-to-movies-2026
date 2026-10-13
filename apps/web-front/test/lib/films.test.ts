import { describe, expect, it } from "vitest";
import { groupByFilm } from "../../src/lib/films.ts";
import { screening } from "../fixtures.ts";

describe("groupByFilm", () => {
  it("lists each film once, in order of its first show, with its shows in order", () => {
    const other = { ...screening().film, id: "tmdb:2", title: "Toinen" };
    const groups = groupByFilm([
      screening({ id: "a", startsAt: "2026-10-13T20:00:00+03:00" }),
      screening({ id: "b", startsAt: "2026-10-13T17:00:00+03:00", film: other }),
      screening({ id: "c", startsAt: "2026-10-13T12:00:00+03:00" }),
    ]);
    expect(groups.map((g) => g.film.title)).toEqual(["Unohdettu saari", "Toinen"]);
    expect(groups[0]?.screenings.map((s) => s.id)).toEqual(["c", "a"]);
  });
});
