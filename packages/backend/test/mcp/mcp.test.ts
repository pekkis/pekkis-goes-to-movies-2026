import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import type { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";
import { sql } from "kysely";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createApp } from "../../src/api/app.ts";
import { createDb } from "../../src/db/database.ts";
import { ingestBatch, ingestFilms } from "../../src/ingest/ingest.ts";
import { batch, catalog, film, screening } from "../factory.ts";

const TOKEN = "test-token-abcdefghijklmnopqrstuvwxyz";
const db = createDb(process.env["TEST_DATABASE_URL"]!);
const app = createApp({ db, mcpToken: TOKEN });

/** The official MCP client, talking to the app in-process (no network). */
const connect = async () => {
  const client = new Client({ name: "test", version: "1.0.0" });
  const transport = new StreamableHTTPClientTransport(new URL(`http://localhost/mcp/${TOKEN}`), {
    fetch: async (input, init) => app.request(String(input), init),
  });
  // The SDK's client and transport types disagree under exactOptionalPropertyTypes.
  await client.connect(transport as unknown as Transport);
  return client;
};

type CallResult = { content: { type: string; text: string }[] };
const call = async (client: Client, name: string, args: Record<string, unknown>) => {
  const result = (await client.callTool({ name, arguments: args })) as CallResult;
  return JSON.parse(result.content[0]!.text) as any;
};

beforeAll(async () => {
  await sql`truncate screenings, film_listings, auditoriums, venues, providers, films cascade`.execute(
    db,
  );
  await ingestFilms(db, catalog([film()]));
  const b = batch([
    screening("1"), // 18:00 Jyväskylä, tmdb:100
    screening("2", { startsAt: "2026-10-10T20:30:00+03:00" }),
    // After midnight, still on the 10th's programme.
    screening("3", { startsAt: "2026-10-11T00:30:00+03:00" }),
    screening("4", {
      venueId: "testchain:venue:2",
      auditoriumId: undefined,
      startsAt: "2026-10-10T19:00:00+03:00",
    }),
  ]);
  b.venues.push({
    id: "testchain:venue:2",
    provider: "testchain",
    sourceId: "2",
    name: "Pääkino",
    city: "Helsinki",
    geo: { lat: 60.17, lon: 24.94 },
  });
  await ingestBatch(db, b);
});
afterAll(() => db.destroy());

describe("MCP endpoint", () => {
  it("exists only at the token path, and only when a token is set", async () => {
    expect((await app.request("/mcp/wrong-token", { method: "POST" })).status).toBe(404);
    const without = createApp({ db });
    expect((await without.request(`/mcp/${TOKEN}`, { method: "POST" })).status).toBe(404);
  });

  it("offers three read-only tools", async () => {
    const client = await connect();
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).toSorted()).toEqual(["find_film", "list_venues", "whats_on"]);
    expect(tools.every((t) => t.annotations?.readOnlyHint)).toBe(true);
    expect(client.getInstructions()).toContain("not endorsed or certified by TMDB");
    await client.close();
  });
});

describe("logging", () => {
  it("keeps the token out of the request log", async () => {
    const lines: string[] = [];
    const original = console.log;
    console.log = (...args: unknown[]) => lines.push(args.join(" "));
    try {
      const logged = createApp({ db, mcpToken: TOKEN, log: true });
      await logged.request(`/mcp/${TOKEN}`, { method: "GET" });
    } finally {
      console.log = original;
    }
    expect(lines.join("\n")).toContain("/mcp/…");
    expect(lines.join("\n")).not.toContain(TOKEN);
  });
});

describe("tools", () => {
  it("whats_on: a city's day in start order, with the cinema's ticket link", async () => {
    const client = await connect();
    const day = await call(client, "whats_on", { date: "2026-10-10", city: "jyväskylä" });
    expect(day.screenings.map((s: { time: string }) => s.time)).toEqual([
      "18:00",
      "20:30",
      "00:30",
    ]);
    expect(day.screenings[0]).toMatchObject({
      film: { id: "tmdb:100", title: "Testielokuva" },
      venue: { name: "Testikino", city: "Jyväskylä" },
      ticket_url: expect.stringMatching(/^https:/),
    });
    // Critics' scores only on request.
    expect(day.screenings[0].film).not.toHaveProperty("ratings");
    const rated = await call(client, "whats_on", {
      date: "2026-10-10",
      city: "Jyväskylä",
      include_ratings: true,
    });
    expect(rated.screenings[0].film.ratings.length).toBeGreaterThan(0);
    await client.close();
  });

  it("whats_on: time windows count the night to the programme day", async () => {
    const client = await connect();
    const late = await call(client, "whats_on", { date: "2026-10-10", after: "20:00" });
    expect(late.screenings.map((s: { time: string }) => s.time)).toEqual(["20:30", "00:30"]);
    const early = await call(client, "whats_on", { date: "2026-10-10", before: "20:00" });
    expect(early.screenings.map((s: { time: string }) => s.time)).toEqual(["18:00", "19:00"]);
    await client.close();
  });

  it("whats_on: near a point, with distances", async () => {
    const client = await connect();
    const near = await call(client, "whats_on", {
      date: "2026-10-10",
      near: { lat: 60.17, lon: 24.95, radius_km: 5 },
    });
    expect(near.screenings).toHaveLength(1);
    expect(near.screenings[0]).toMatchObject({ venue: { city: "Helsinki" }, distance_km: 0.6 });
    await client.close();
  });

  it("find_film and list_venues", async () => {
    const client = await connect();
    const found = await call(client, "find_film", { query: "testielokuv" });
    expect(found.films[0]).toMatchObject({ id: "tmdb:100", title: "Testielokuva" });
    const venues = await call(client, "list_venues", { city: "Helsinki" });
    expect(venues.venues.map((v: { name: string }) => v.name)).toEqual(["Pääkino"]);
    await client.close();
  });
});
