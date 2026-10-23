import reactRenderer from "@astrojs/react/server.js";
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import VenuePage from "../../src/pages/fi/elokuvateatterit/[venue].astro";
import { fakeFetch, NOON_INSTANT, screening, venue } from "../fixtures.ts";

let container: AstroContainer;
beforeAll(async () => {
  container = await AstroContainer.create();
  container.addServerRenderer({ renderer: reactRenderer, name: "@astrojs/react" });
  container.addClientRenderer({ name: "@astrojs/react", entrypoint: "@astrojs/react/client.js" });
});

const api = createApi(
  "http://api",
  fakeFetch({
    "/v1/venues": [
      venue({
        address: "Kauppakatu 1",
        postalCode: "40100",
        provider: {
          id: "testchain",
          name: "Test Chain",
          homepage: "https://kino.example/",
          booking: "buy",
        },
      }),
    ],
    "/v1/screenings": { date: "2026-10-13", items: [screening()], nextCursor: null },
  }).impl,
);

const renderVenue = (slug: string) =>
  container.renderToResponse(VenuePage, {
    params: { venue: slug },
    request: new Request(`http://web/fi/elokuvateatterit/${slug}`),
    locals: { api, now: NOON_INSTANT },
  });

describe("venue page", () => {
  it("renders the venue's films for the day, with address, map and website", async () => {
    const res = await renderVenue("kino-testi-jyvaskyla");
    const html = await res.text();
    expect(res.status).toBe(200);
    expect(html).toContain("<h1>Kino Testi</h1>");
    expect(html).toContain("Kauppakatu 1, 40100 Jyväskylä");
    expect(html).toContain("https://www.openstreetmap.org/?mlat=62.24&amp;mlon=25.75");
    expect(html).toContain('href="https://kino.example/"');
    expect(html).toContain('href="/fi/kaupungit/jyvaskyla"');
    expect(html).toContain("Unohdettu saari");
    expect(html).toContain('href="https://kino.example/liput/1"');
    expect(html).toContain("1 elokuva");
    expect(html.match(/<astro-island/g)).toHaveLength(1);
    // When its programme was last read; no notice while its source answers.
    expect(html).toContain("Näytökset päivitetty 13.10. klo 08.00");
    expect(html).not.toContain("ei vastannut");
  });

  it("says when the cinema's site did not answer at the latest pull", async () => {
    const down = createApi(
      "http://api",
      fakeFetch({
        "/v1/venues": [
          venue({
            lastCheck: {
              status: "failed",
              checkedAt: "2026-10-14T05:00:00.000Z",
              message: "Request failed with status code 503",
            },
          }),
        ],
        "/v1/screenings": { date: "2026-10-13", items: [screening()], nextCursor: null },
      }).impl,
    );
    const res = await container.renderToResponse(VenuePage, {
      params: { venue: "kino-testi-jyvaskyla" },
      request: new Request("http://web/fi/elokuvateatterit/kino-testi-jyvaskyla"),
      locals: { api: down, now: NOON_INSTANT },
    });
    const html = await res.text();
    expect(html).toContain("Näytökset päivitetty 13.10. klo 08.00");
    expect(html).toContain("Teatterin sivu ei vastannut viimeisimmässä haussa (14.10. klo 08.00)");
  });

  it("answers 404 for an unknown venue", async () => {
    expect((await renderVenue("kino-testi")).status).toBe(404);
  });
});
