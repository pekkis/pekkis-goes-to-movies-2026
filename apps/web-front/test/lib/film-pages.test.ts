import { describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import { loadFilmPage, loadFrontPage } from "../../src/lib/film-pages.ts";
import { fakeFetch, film, screening, venue } from "../fixtures.ts";

const TODAY = "2026-10-13";

const filmApi = (byDate: Record<string, number>) =>
  fakeFetch({
    "/v1/films/tmdb:1185806": film(),
    "/v1/venues": [venue()],
    "/v1/films/tmdb:1185806/screenings": (url: URL) => {
      const date = url.searchParams.get("date")!;
      return {
        date,
        items: Array.from({ length: byDate[date] ?? 0 }, (_, i) =>
          screening({
            id: `${date}-${i}`,
            businessDate: date,
            startsAt: `${date}T18:0${i}:00+03:00`,
          }),
        ),
        nextCursor: null,
      };
    },
  });

describe("loadFilmPage", () => {
  it("counts the next seven days and opens on the first with screenings", async () => {
    const fake = filmApi({ "2026-10-14": 2, "2026-10-16": 1 });
    const page = await loadFilmPage(
      createApi("http://api", fake.impl),
      "unohdettu-saari-1185806",
      null,
      TODAY,
    );
    expect(page?.kind).toBe("film");
    if (page?.kind !== "film") {
      return;
    }
    expect(page.days.map((d) => d.count)).toEqual([0, 2, 0, 1, 0, 0, 0]);
    expect(page.date).toBe("2026-10-14");
    expect(page.screenings).toHaveLength(2);
    expect(page.providers["testchain:venue:1"]).toEqual({ id: "testchain", name: "Test Chain" });
  });

  it("shows a chosen day, also one beyond the week", async () => {
    const fake = filmApi({ "2026-10-30": 3 });
    const api = createApi("http://api", fake.impl);
    const page = await loadFilmPage(api, "unohdettu-saari-1185806", "2026-10-30", TODAY);
    expect(page).toMatchObject({ kind: "film", date: "2026-10-30" });
    expect(page?.kind === "film" && page.screenings).toHaveLength(3);
  });

  it("sends an old or partial slug to the film's own path, and knows no listing", async () => {
    const api = createApi("http://api", filmApi({}).impl);
    expect(await loadFilmPage(api, "vanha-nimi-1185806", null, TODAY)).toEqual({
      kind: "redirect",
      path: "/fi/elokuvat/unohdettu-saari-1185806",
    });
    expect(await loadFilmPage(api, "ei-numeroa", null, TODAY)).toBeUndefined();
    expect(await loadFilmPage(api, "jotain-999", null, TODAY)).toBeUndefined();
  });
});

describe("loadFrontPage", () => {
  it("asks for new films still playing this week, coming ones first, each by title", async () => {
    const opening = (id: string, title: string, firstShowing: string) => ({
      film: film({ id, title }),
      firstShowing,
    });
    const fake = fakeFetch({
      "/v1/films/playing": [
        { film: film({ id: "tmdb:9", title: "Thelma ja Louise" }), nextShowing: "2026-10-15" },
        { film: film({ id: "tmdb:8", title: "Casablanca" }), nextShowing: "2026-10-14" },
      ],
      "/v1/films/openings": [
        opening("tmdb:1", "Öljy", "2026-10-09"),
        opening("tmdb:2", "Digger", "2026-10-13"),
        opening("tmdb:3", "Lapin sota", "2026-10-16"),
        opening("tmdb:4", "Avaruusboltsit", "2026-10-11"),
      ],
    });
    const page = await loadFrontPage(createApi("http://api", fake.impl), TODAY);
    expect(page.opened.map((o) => o.film.title)).toEqual(["Avaruusboltsit", "Digger", "Öljy"]);
    expect(page.coming.map((o) => o.film.title)).toEqual(["Lapin sota"]);
    const asked = fake.requests.find((u) => u.pathname === "/v1/films/openings")!;
    // First showing from a week back to six days ahead; playing in today and the next six.
    expect(
      ["from", "to", "playingFrom", "playingTo", "excludeTag"].map((k) =>
        asked.searchParams.get(k),
      ),
    ).toEqual(["2026-10-06", "2026-10-19", "2026-10-13", "2026-10-19", "classic"]);
    // Classics playing this week, by title.
    expect(page.classics.map((c) => c.film.title)).toEqual(["Casablanca", "Thelma ja Louise"]);
    const classics = fake.requests.find((u) => u.pathname === "/v1/films/playing")!;
    expect(["from", "to", "tag"].map((k) => classics.searchParams.get(k))).toEqual([
      "2026-10-13",
      "2026-10-19",
      "classic",
    ]);
  });
});
