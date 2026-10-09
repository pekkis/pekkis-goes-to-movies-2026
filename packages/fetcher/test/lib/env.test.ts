import { expect, it } from "vitest";
import { loadEnv } from "../../src/lib/env.ts";

it("accepts a v4 token and an optional contact", () => {
  expect(loadEnv({ TMDB_APIKEY: "eyJabc", CONTACT: "me@example.com" })).toEqual({
    TMDB_APIKEY: "eyJabc",
    CONTACT: "me@example.com",
  });
  expect(loadEnv({ TMDB_APIKEY: "eyJabc" })).toEqual({ TMDB_APIKEY: "eyJabc" });
});

it("lists every problem at once", () => {
  expect(() => loadEnv({ CONTACT: "" })).toThrow(/TMDB_APIKEY[\s\S]*CONTACT/);
});

it("rejects a v3 API key", () => {
  expect(() => loadEnv({ TMDB_APIKEY: "0123456789abcdef" })).toThrow(/v4 read access token/);
});
