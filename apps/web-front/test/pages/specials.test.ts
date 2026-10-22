import reactRenderer from "@astrojs/react/server.js";
import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import { createApi } from "../../src/lib/api.ts";
import SpecialsPage from "../../src/pages/fi/erikoisnaytokset.astro";
import { fakeFetch, NOON_INSTANT, screening } from "../fixtures.ts";

let container: AstroContainer;
beforeAll(async () => {
  container = await AstroContainer.create();
  container.addServerRenderer({ renderer: reactRenderer, name: "@astrojs/react" });
  container.addClientRenderer({ name: "@astrojs/react", entrypoint: "@astrojs/react/client.js" });
});

const fake = fakeFetch({
  "/v1/series": [
    { id: "neulekino", name: "Neulekino", kind: "strand", screenings: 1, firstDay: "2026-10-15" },
  ],
  "/v1/screenings": {
    date: "2026-10-13",
    items: [screening({ businessDate: "2026-10-15", series: ["Neulekino"] })],
    nextCursor: null,
  },
});
const api = createApi("http://api", fake.impl);

const render = async (query = "") => {
  const res = await container.renderToResponse(SpecialsPage, {
    request: new Request(`http://web/fi/erikoisnaytokset${query}`),
    locals: { api, now: NOON_INSTANT },
  });
  return { res, html: await res.text() };
};

describe("special screenings page", () => {
  it("offers every tag and the coming series as checkboxes in a GET form", async () => {
    const { res, html } = await render();
    expect(res.status).toBe(200);
    expect(html).toMatch(/<form [^>]*action="\/fi\/erikoisnaytokset" method="get"/);
    expect(html).toMatch(/<input type="checkbox" name="tunniste" value="domestic"/);
    expect(html).toContain("Kotimaiset elokuvat");
    expect(html).toMatch(/<input type="checkbox" name="sarja" value="neulekino"/);
    expect(html).toContain("1 näytös, to 15.10. alkaen");
    expect(html).toContain("Valitse ainakin yksi laji tai sarja.");
    expect(html).toContain("<title>Erikoisnäytökset | Pekkis goes to movies</title>");
    expect(html).not.toContain("<astro-island");
  });

  it("shows a shared address's choices checked, and their screenings by day", async () => {
    const { html } = await render("?sarja=neulekino");
    expect(html).toMatch(/<input type="checkbox" name="sarja" checked="" value="neulekino"/);
    expect(html).toContain("<astro-island");
    expect(html).toContain("torstaina 15.10.");
    // The choices first, the form folded away.
    expect(html).toContain("<title>Erikoisnäytökset: Neulekino | Pekkis goes to movies</title>");
    expect(html).toContain("Valittu: Neulekino");
    expect(html).toContain("· Neulekino");
    expect(html).toMatch(/<details[^>]*><summary>Muuta valintoja<\/summary><form/);
    expect(html).toContain("Liput");
  });
});
