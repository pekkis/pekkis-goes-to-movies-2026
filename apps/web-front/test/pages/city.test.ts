import reactRenderer from "@astrojs/react/server.js";
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import CityPage from "../../src/pages/fi/kaupungit/[city].astro";
import { fakeFetch, screening, venue } from "../fixtures.ts";

let container: AstroContainer;
beforeAll(async () => {
  container = await AstroContainer.create();
  container.addServerRenderer({ renderer: reactRenderer, name: "@astrojs/react" });
});

const api = createApi(
  "http://api",
  fakeFetch({
    "/v1/venues": [venue()],
    "/v1/screenings": { date: "2026-10-13", items: [screening()], nextCursor: null },
  }).impl,
);

const renderCity = (city: string, query = "") =>
  container.renderToResponse(CityPage, {
    params: { city },
    request: new Request(`http://web/fi/kaupungit/${city}${query}`),
    locals: { api },
  });

describe("city page", () => {
  it("renders the day's screenings on the server, kept out of search engines", async () => {
    const res = await renderCity("jyvaskyla");
    const html = await res.text();
    expect(res.status).toBe(200);
    expect(html).toContain("Elokuvat Jyväskylä");
    expect(html).toContain("tiistaina 13.10.");
    expect(html).toContain("Unohdettu saari");
    expect(html).toContain('href="https://kino.example/liput/1"');
    expect(html).toMatch(/<meta name="robots" content="noindex, nofollow">/);
    // No islands: the page is plain HTML and loads no JavaScript.
    expect(html).not.toContain("<astro-island");
    expect(html).toMatch(/<input [^>]*type="date"/);
    expect(html).toContain('href="?date=2026-10-14"');
    // TMDB's terms: logo and notice on every page.
    expect(html).toContain('src="/tmdb-logo.svg"');
    expect(html).toContain("not endorsed or certified by TMDB");
  });

  it("answers 404 for an unknown city", async () => {
    const res = await renderCity("nowhere");
    expect(res.status).toBe(404);
  });
});
