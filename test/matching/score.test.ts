import { describe, expect, it } from "vitest";
import { decide, gatherEvidence, tierOf, type Evidence } from "../../src/matching/score.ts";
import { details } from "../tmdb/factory.ts";

const YEAR = 2026;
const listing = { title: "The Odyssey", runtimeMinutes: 172, countries: ["GB", "US"] };

describe("gatherEvidence", () => {
  it("matches the Finnish title through translations", () => {
    const e = gatherEvidence(
      { title: "Verityn varjo", runtimeMinutes: 117, countries: ["US"] },
      details({
        id: 1,
        title: "Verity",
        runtime: 114,
        translations: {
          translations: [{ iso_639_1: "fi", iso_3166_1: "FI", data: { title: "Verityn varjo" } }],
        },
      }),
      YEAR,
    );
    expect(e).toEqual({
      tmdbId: 1,
      title: "exact",
      year: "window",
      runtime: "close",
      countries: "overlap",
      rating: "unknown",
    });
  });

  it("classifies runtime differences", () => {
    const runtime = (minutes: number) =>
      gatherEvidence(listing, details({ id: 1, title: "The Odyssey", runtime: minutes }), YEAR)
        .runtime;
    expect(runtime(173)).toBe("close");
    expect(runtime(165)).toBe("near");
    expect(runtime(86)).toBe("far");
  });

  it("treats a numbered sequel of a brand-new film as a prefix match", () => {
    const e = gatherEvidence(
      { title: "Practical Magic: Lumotut sisaret", runtimeMinutes: 130, countries: ["US"] },
      details({ id: 2, title: "Practical Magic 2", runtime: 130, release_date: "2026-09-09" }),
      YEAR,
    );
    expect(e.title).toBe("prefix");
  });

  it("does not treat another film of the same franchise as a prefix match (regression)", () => {
    const e = gatherEvidence(
      { title: "Ryhmä Hau: Dinoelokuva", runtimeMinutes: 88, countries: ["CA", "US"] },
      details({
        id: 893723,
        title: "Ryhmä Hau: Mahtipennut",
        original_title: "PAW Patrol: The Mighty Movie",
        runtime: 88,
        release_date: "2023-09-21",
        production_countries: [{ iso_3166_1: "US" }],
      }),
      YEAR,
    );
    expect(e.title).toBe("none");
    expect(tierOf(e)).toBeUndefined();
  });

  it("does not prefix-match an old film even with the bare prefix as title", () => {
    const e = gatherEvidence(
      { title: "Practical Magic: Lumotut sisaret", runtimeMinutes: 130, countries: ["US"] },
      details({ id: 6435, title: "Practical Magic", runtime: 104, release_date: "1998-10-16" }),
      YEAR,
    );
    expect(e.title).toBe("none");
  });
});

const ev = (overrides: Partial<Evidence>): Evidence => ({
  tmdbId: 1,
  title: "exact",
  year: "window",
  runtime: "close",
  countries: "overlap",
  rating: "unknown",
  ...overrides,
});

describe("tierOf", () => {
  it.each<[Partial<Evidence>, string | undefined]>([
    [{}, "exact"],
    [{ runtime: "unknown" }, "exact"],
    [{ countries: "unknown", runtime: "near" }, "exact"],
    [{ runtime: "far" }, undefined],
    [{ countries: "disjoint" }, undefined],
    [{ year: "outside" }, "exact"],
    [{ year: "outside", runtime: "near" }, undefined],
    [{ runtime: "unknown", countries: "unknown" }, "sparse"],
    [{ runtime: "unknown", countries: "unknown", year: "outside" }, undefined],
    [{ title: "prefix" }, "prefix"],
    [{ title: "prefix", runtime: "near" }, undefined],
    [{ title: "none" }, undefined],
  ])("%o -> %s", (overrides, expected) => {
    expect(tierOf(ev(overrides))).toBe(expected);
  });
});

describe("decide", () => {
  it("prefers an exact match over a prefix match (Insidious)", () => {
    expect(decide([ev({ tmdbId: 1 }), ev({ tmdbId: 2, title: "prefix" })])).toEqual({
      kind: "match",
      tmdbId: 1,
      tier: "exact",
    });
  });

  it("refuses to choose between two candidates nothing tells apart", () => {
    expect(decide([ev({ tmdbId: 1 }), ev({ tmdbId: 2 })])).toEqual({
      kind: "none",
      reason: "ambiguous (exact): 1, 2",
    });
  });

  it("accepts a sparse TMDB record only when it is alone", () => {
    const sparse = { runtime: "unknown", countries: "unknown" } as const;
    expect(decide([ev({ tmdbId: 1, ...sparse })])).toMatchObject({ kind: "match", tier: "sparse" });
    expect(decide([ev({ tmdbId: 1, ...sparse }), ev({ tmdbId: 2, ...sparse })])).toMatchObject({
      kind: "none",
    });
  });

  it("breaks a tie on runtime, then on the Finnish rating (The Furious)", () => {
    expect(
      decide([ev({ tmdbId: 1, runtime: "near" }), ev({ tmdbId: 2, runtime: "close" })]),
    ).toMatchObject({ kind: "match", tmdbId: 2 });
    expect(
      decide([ev({ tmdbId: 1, rating: "different" }), ev({ tmdbId: 2, rating: "same" })]),
    ).toMatchObject({ kind: "match", tmdbId: 2 });
    expect(decide([ev({ tmdbId: 1 }), ev({ tmdbId: 2 })])).toMatchObject({ kind: "none" });
  });

  it("explains why nothing matched", () => {
    expect(decide([])).toEqual({ kind: "none", reason: "no search results" });
    expect(decide([ev({ title: "none" })])).toMatchObject({
      kind: "none",
      reason: expect.stringContaining("not confident"),
    });
  });
});
