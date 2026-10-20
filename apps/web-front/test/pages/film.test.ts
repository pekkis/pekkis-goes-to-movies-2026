import reactRenderer from "@astrojs/react/server.js";
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import FilmPage from "../../src/pages/fi/elokuvat/[film].astro";
import FrontPage from "../../src/pages/fi/index.astro";
import { fakeFetch, film, NOON_INSTANT, screening, venue } from "../fixtures.ts";

let container: AstroContainer;
beforeAll(async () => {
  container = await AstroContainer.create();
  container.addServerRenderer({ renderer: reactRenderer, name: "@astrojs/react" });
  container.addClientRenderer({ name: "@astrojs/react", entrypoint: "@astrojs/react/client.js" });
});

const api = createApi(
  "http://api",
  fakeFetch({
    "/v1/venues": [venue()],
    "/v1/films/tmdb:1185806": film(),
    "/v1/films/tmdb:1185806/screenings": (url: URL) => ({
      date: url.searchParams.get("date"),
      items: url.searchParams.get("date") === "2026-10-13" ? [screening()] : [],
      nextCursor: null,
    }),
    "/v1/films/openings": [{ film: film(), firstShowing: "2026-10-15" }],
    "/v1/films/playing": [
      { film: film({ id: "tmdb:251", title: "Ghost" }), nextShowing: "2026-10-14" },
    ],
  }).impl,
);

const renderFilm = (slug: string, query = "") =>
  container.renderToResponse(FilmPage, {
    params: { film: slug },
    request: new Request(`http://web/fi/elokuvat/${slug}${query}`),
    locals: { api, now: NOON_INSTANT },
  });

describe("film page", () => {
  it("renders the film from TMDB, its days, and the day's screenings in an island", async () => {
    const res = await renderFilm("unohdettu-saari-1185806");
    const html = await res.text();
    expect(res.status).toBe(200);
    expect(html).toContain("<h1>Unohdettu saari</h1>");
    expect(html).toContain('src="https://image.tmdb.org/t/p/w342/saari.jpg"');
    expect(html).toContain("Kaksi ystävää ja saari.");
    expect(html).toContain("Ensi-ilta Suomessa: 2.10.2026");
    expect(html).toContain('href="https://www.youtube.com/watch?v=abc123"');
    expect(html).toMatch(/aria-current="date"[^>]*>ti 13\.10\. \(1\)/);
    expect(html).toContain('href="https://kino.example/liput/1"');
    expect(html.match(/<astro-island/g)).toHaveLength(1);
    // Ratings are opt-in: none on the film page.
    expect(html).not.toContain("Rotten");
  });

  it("sends an old slug to the film's path, keeping the day", async () => {
    const res = await renderFilm("vanha-1185806", "?date=2026-10-14");
    expect(res.status).toBe(301);
    expect(res.headers.get("location")).toBe(
      "/fi/elokuvat/unohdettu-saari-1185806?date=2026-10-14",
    );
  });

  it("answers 404 for an unknown film", async () => {
    expect((await renderFilm("ei-ole-999")).status).toBe(404);
  });
});

describe("front page", () => {
  it("lists the new films with posters, linking to their pages", async () => {
    const res = await container.renderToResponse(FrontPage, {
      request: new Request("http://web/fi/"),
      locals: { api, now: NOON_INSTANT },
    });
    const html = await res.text();
    expect(html).toContain("Uudet elokuvat");
    // Coming premieres before the ones already started.
    expect(html.indexOf("Alkamassa viikon aikana")).toBeLessThan(
      html.indexOf("Alkaneet viikon aikana"),
    );
    expect(html).toContain('href="/fi/elokuvat/unohdettu-saari-1185806"');
    expect(html).toContain('src="https://image.tmdb.org/t/p/w154/saari.jpg"');
    expect(html).toContain("1. näytös to 15.10.");
    // Re-runs after the new films, with their next showing.
    expect(html.indexOf("Uusintaesitykset")).toBeGreaterThan(
      html.indexOf("Alkaneet viikon aikana"),
    );
    expect(html).toContain('href="/fi/elokuvat/ghost-251"');
    expect(html).toContain("seuraava näytös ke 14.10.");
    expect(html).toContain('href="/fi/kaupungit/jyvaskyla"');
  });
});
