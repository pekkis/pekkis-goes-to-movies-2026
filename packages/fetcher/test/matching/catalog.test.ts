import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ProviderBatch, type FilmListing, type Screening } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import { buildCatalog } from "../../src/matching/catalog.ts";
import type { TmdbClient } from "../../src/tmdb/client.ts";
import { details } from "../tmdb/factory.ts";

const NOW = new Date("2026-10-20T06:00:00.000Z");

const listing = (id: string, title: string, over: Partial<FilmListing> = {}): FilmListing => ({
  id: `kino:film:${id}`,
  provider: "kino",
  sourceId: id,
  title: { fi: title },
  genres: [],
  countries: [],
  kind: "film",
  ...over,
});

const screening = (id: string, listingId: string): Screening => ({
  id: `kino:show:${id}`,
  provider: "kino",
  sourceId: id,
  venueId: "kino:venue:1",
  listingId,
  startsAt: "2026-10-21T18:00:00+03:00",
  businessDate: "2026-10-21",
  presentation: { projection: "digital", dimension: "2d", formats: [] },
  audio: [],
  subtitles: { kind: "unknown" },
  tags: [],
  series: [],
  availability: "unknown",
  unmappedLabels: [],
  fetchedAt: "2026-10-20T06:00:00.000Z",
});

const noSearch: TmdbClient = {
  search: async () => [],
  movie: async (id) =>
    details({
      id,
      title: id === 251 ? "Ghost" : "New",
      release_date: id === 251 ? "1990-07-13" : "2025-01-01",
    }),
  findByImdb: async () => undefined,
};

describe("buildCatalog", () => {
  it("tags screenings of films released CLASSIC_AGE_YEARS ago or more as classics", async () => {
    const dir = await mkdtemp(join(tmpdir(), "pgtm-catalog-"));
    const batch: ProviderBatch = {
      provider: {
        id: "kino",
        name: "Kino",
        homepage: "https://kino.example",
        platform: "custom",
        booking: "door",
      },
      fetchedAt: "2026-10-20T06:00:00.000Z",
      window: { from: "2026-10-20", to: "2026-10-26" },
      venues: [
        { id: "kino:venue:1", provider: "kino", sourceId: "1", name: "Kino", city: "Kuopio" },
      ],
      auditoriums: [],
      listings: [
        listing("ghost", "Ghost"),
        listing("new", "New"),
        // Not on TMDB: the cinema's own year decides.
        listing("local", "Paikallinen dokumentti", { year: 2015 }),
      ],
      screenings: [
        screening("1", "kino:film:ghost"),
        screening("2", "kino:film:new"),
        screening("3", "kino:film:local"),
      ],
      warnings: [],
    };
    await writeFile(join(dir, "kino.json"), JSON.stringify(batch));
    await buildCatalog(
      dir,
      noSearch,
      {
        "kino:film:ghost": { tmdb: 251, title: "Ghost" },
        "kino:film:new": { tmdb: 999, title: "New" },
        "kino:film:local": { tmdb: null, title: "Paikallinen dokumentti" },
      },
      NOW,
    );
    const written = ProviderBatch.parse(JSON.parse(await readFile(join(dir, "kino.json"), "utf8")));
    expect(written.screenings.map((s) => [s.sourceId, s.filmId ?? null, s.tags])).toEqual([
      ["1", "tmdb:251", ["classic"]],
      ["2", "tmdb:999", []],
      ["3", null, ["classic"]],
    ]);
  });
});
