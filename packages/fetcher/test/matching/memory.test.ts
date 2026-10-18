import type { FilmListing } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import { remember, sameRuntime } from "../../src/matching/memory.ts";

const NOW = new Date("2026-10-18T06:00:00.000Z");
const listing = (id: string, title: string): FilmListing => ({
  id,
  provider: "biorex",
  sourceId: id,
  title: { fi: title },
  runtimeMinutes: 100,
  genres: [],
  countries: [],
  kind: "film",
});

describe("the link memory", () => {
  it.each([
    [100, 103, true],
    [100, 104, false],
    [undefined, undefined, true],
    [100, undefined, false],
  ])("sameRuntime(%s, %s) = %s", (a, b, same) => {
    expect(sameRuntime(a, b)).toBe(same);
  });

  it("remembers certain links, never aliases, and keeps unseen ones until they fade", () => {
    const old = {
      gone: { filmId: "tmdb:1", titleKey: "a", lastSeen: "2026-09-01T00:00:00.000Z" },
      ancient: { filmId: "tmdb:2", titleKey: "b", lastSeen: "2026-01-01T00:00:00.000Z" },
    };
    const links = new Map([
      ["auto", { filmId: "tmdb:3", method: "auto" }],
      ["alias", { filmId: "tmdb:4", method: "alias" }],
    ]);
    const next = remember(old, [listing("auto", "Digger"), listing("alias", "Kana")], links, NOW);
    expect(Object.keys(next).toSorted()).toEqual(["auto", "gone"]);
    expect(next["auto"]).toEqual({
      filmId: "tmdb:3",
      titleKey: "digger",
      runtimeMinutes: 100,
      lastSeen: NOW.toISOString(),
    });
  });
});
