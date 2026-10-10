import { hc } from "hono/client";
import { afterAll, describe, expect, it } from "vitest";
import { createApp } from "../../src/api/app.ts";
import { createDb } from "../../src/db/database.ts";
import type { AppType } from "../../src/index.ts";

const db = createDb(process.env["TEST_DATABASE_URL"]!);
const app = createApp({ db });

// The typed client a React app would use, wired to the app in-process.
const api = hc<AppType>("http://localhost", {
  fetch: (input: string | URL | Request, init?: RequestInit) => app.request(input, init),
});

afterAll(() => db.destroy());

describe("typed client (hono/client)", () => {
  it("calls routes with typed parameters and typed responses", async () => {
    const res = await api.v1.health.$get();
    const body = await res.json();
    // `ok` is typed as boolean: a typo here would fail `pnpm typecheck`.
    expect(body.ok).toBe(true);

    const venues = await api.v1.venues.$get({ query: { city: "Nowhere" } });
    expect(venues.status).toBe(200);
    if (venues.status === 200) expect(await venues.json()).toEqual([]);

    const film = await api.v1.films[":id"].$get({ param: { id: "tmdb:404404" } });
    expect(film.status).toBe(404);
  });
});
