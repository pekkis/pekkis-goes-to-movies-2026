import { expect, it } from "vitest";
import { loadEnv, requireTmdbKey } from "../../src/lib/env.ts";

it("accepts a v4 token and an optional contact", () => {
  expect(loadEnv({ TMDB_APIKEY: "eyJabc", CONTACT: "me@example.com" })).toEqual({
    TMDB_APIKEY: "eyJabc",
    CONTACT: "me@example.com",
  });
  expect(loadEnv({ TMDB_APIKEY: "eyJabc" })).toEqual({ TMDB_APIKEY: "eyJabc" });
});

it("lists every problem at once", () => {
  expect(() => loadEnv({ TMDB_APIKEY: "abc", CONTACT: "" })).toThrow(/TMDB_APIKEY[\s\S]*CONTACT/);
});

it("leaves the TMDB token optional until a command needs it", () => {
  // venues:locate runs without one; pull and match ask for it up front.
  const env = loadEnv({});
  expect(env).toEqual({});
  expect(() => requireTmdbKey(env)).toThrow(/TMDB_APIKEY is not set/);
  expect(requireTmdbKey(loadEnv({ TMDB_APIKEY: "eyJabc" }))).toBe("eyJabc");
});

it("rejects a v3 API key", () => {
  expect(() => loadEnv({ TMDB_APIKEY: "0123456789abcdef" })).toThrow(/v4 read access token/);
});
