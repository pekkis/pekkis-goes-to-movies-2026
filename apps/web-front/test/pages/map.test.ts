import reactRenderer from "@astrojs/react/server.js";
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import MapPage from "../../src/pages/fi/kartta.astro";
import { fakeFetch, NOON, venue } from "../fixtures.ts";

let container: AstroContainer;
beforeAll(async () => {
  container = await AstroContainer.create();
  container.addServerRenderer({ renderer: reactRenderer, name: "@astrojs/react" });
});

describe("map page", () => {
  it("renders every venue as a list by city, with the map's data alongside", async () => {
    const api = createApi(
      "http://api",
      fakeFetch({
        "/v1/venues": [
          venue(),
          venue({ id: "x:venue:2", name: "Plevna Tampere", city: "Tampere" }),
        ],
      }).impl,
    );
    const res = await container.renderToResponse(MapPage, {
      request: new Request("http://web/fi/kartta"),
      locals: { api, now: NOON },
    });
    const html = await res.text();
    expect(res.status).toBe(200);
    expect(html).toContain('href="/fi/elokuvateatterit/kino-testi-jyvaskyla"');
    expect(html).toContain('href="/fi/elokuvateatterit/plevna-tampere"');
    expect(html).toContain('href="/fi/kaupungit/tampere"');
    // The map container starts hidden and carries the venues as GeoJSON for the script.
    expect(html).toMatch(
      /<div id="venue-map"[^>]*data-venues="[^"]*FeatureCollection[^"]*"[^>]*hidden/,
    );
  });
});
