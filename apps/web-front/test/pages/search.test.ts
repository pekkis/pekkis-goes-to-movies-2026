import reactRenderer from "@astrojs/react/server.js";
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import SearchPage from "../../src/pages/fi/haku.astro";
import { fakeFetch, NOON_INSTANT, screening, venue } from "../fixtures.ts";

let container: AstroContainer;
beforeAll(async () => {
  container = await AstroContainer.create();
  container.addServerRenderer({ renderer: reactRenderer, name: "@astrojs/react" });
  container.addClientRenderer({ name: "@astrojs/react", entrypoint: "@astrojs/react/client.js" });
});

const fake = fakeFetch({
  "/v1/venues": [venue()],
  "/v1/screenings": {
    date: "2026-10-13",
    items: [screening({ venue: { ...screening().venue, geo: { lat: 62.24, lon: 25.75 } } })],
    nextCursor: null,
  },
});
const api = createApi("http://api", fake.impl);

const renderSearch = async (query = "") => {
  const res = await container.renderToResponse(SearchPage, {
    request: new Request(`http://web/fi/haku${query}`),
    locals: { api, now: NOON_INSTANT },
  });
  return { res, html: await res.text() };
};

describe("search page", () => {
  it("starts with the form alone: days from today, cities and the location island", async () => {
    const { res, html } = await renderSearch();
    expect(res.status).toBe(200);
    expect(html).toContain("Hae elokuvaa");
    expect(html).toContain("<title>Hae elokuvaa | Pekkis goes to movies</title>");
    expect(html).toMatch(/<form [^>]*action="\/fi\/haku" method="get"/);
    expect(html).toMatch(/<input type="checkbox" name="paiva" checked="" value="2026-10-13"/);
    expect(html).toContain("tänään ti 13.10.");
    expect(html).toContain('<option value="jyvaskyla">Jyväskylä</option>');
    expect(html).toContain("Valitse paikka tai kirjoita elokuvan nimi");
    // Only the location button is an island until there are results.
    expect(html.match(/<astro-island/g)).toHaveLength(1);
  });

  it("renders the screenings around a city on the server, then narrows them in an island", async () => {
    const { html } = await renderSearch("?kaupunki=jyvaskyla&sade=10");
    expect(html).toContain("Jyväskylä, enintään 10 km");
    // The title says what was searched for, for tabs, bookmarks and shared links.
    expect(html).toContain(
      "<title>Haku: Jyväskylä, enintään 10 km · ti 13.10. | Pekkis goes to movies</title>",
    );
    expect(html).toContain("Unohdettu saari");
    expect(html).toContain('href="https://kino.example/liput/1"');
    expect(html).toContain("Kellonaika");
    expect(html.match(/<astro-island/g)).toHaveLength(2);
    expect(html).toContain('<option value="jyvaskyla" selected="">Jyväskylä</option>');
  });
});
