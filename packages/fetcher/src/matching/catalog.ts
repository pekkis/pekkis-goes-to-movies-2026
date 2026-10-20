import { readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { FilmCatalog, ProviderBatch, type Film } from "@pgtm/model";
import type { TmdbClient } from "../tmdb/client.ts";
import type { Aliases } from "./aliases.ts";
import { matchListings } from "./match.ts";
import { loadMemory, saveMemory } from "./memory.ts";
import { withClassicTag } from "../providers/labels.ts";

export const CATALOG_FILE = "films.json";

const writeJson = (path: string, data: unknown) =>
  writeFile(path, `${JSON.stringify(data, null, 2)}\n`);

/**
 * Matches every listing in `{dir}/*.json` provider batches, writes `filmId` back into
 * the batches and the TMDB films into `{dir}/films.json`.
 */
export const buildCatalog = async (
  dir: string,
  tmdb: TmdbClient,
  aliases: Aliases,
  now: Date = new Date(),
  /** Adds data from other sources (ratings) before the catalog is written. */
  enrich: (films: Film[]) => Promise<Film[]> = async (films) => films,
  /** Where certain links are remembered between runs (memory.ts); none when omitted. */
  memoryPath?: string,
): Promise<FilmCatalog> => {
  const files = (await readdir(dir)).filter((f) => f.endsWith(".json") && f !== CATALOG_FILE);
  const batches = await Promise.all(
    files.map(async (file) => ({
      file,
      batch: ProviderBatch.parse(JSON.parse(await readFile(join(dir, file), "utf8"))),
    })),
  );

  const outcome = await matchListings(
    batches.flatMap(({ batch }) => batch.listings),
    tmdb,
    aliases,
    now,
    memoryPath ? await loadMemory(memoryPath) : {},
  );
  if (memoryPath) {
    await saveMemory(memoryPath, outcome.memory);
  }

  // A film's release year: TMDB's for a matched film, else the cinema's own.
  const filmYears = new Map<string, number>(
    outcome.films.flatMap((f) =>
      f.releaseDate ? [[`tmdb:${f.tmdbId}`, Number(f.releaseDate.slice(0, 4))] as const] : [],
    ),
  );
  const currentYear = now.getUTCFullYear();

  for (const { file, batch } of batches) {
    const listings = batch.listings.map(({ filmId: _f, match: _m, ...listing }) => {
      const link = outcome.links.get(listing.id);
      return link ? { ...listing, filmId: link.filmId, match: link.method } : listing;
    });
    const listingYears = new Map(batch.listings.map((l) => [l.id, l.year]));
    const screenings = batch.screenings.map(({ filmId: _f, ...screening }) => {
      const link = outcome.links.get(screening.listingId);
      const linked = link ? { ...screening, filmId: link.filmId } : screening;
      const year = (link && filmYears.get(link.filmId)) ?? listingYears.get(screening.listingId);
      return withClassicTag(linked, year, currentYear);
    });
    await writeJson(join(dir, file), ProviderBatch.parse({ ...batch, listings, screenings }));
  }

  const catalog = FilmCatalog.parse({
    generatedAt: now.toISOString(),
    films: (await enrich(outcome.films)).toSorted((a, b) => a.tmdbId - b.tmdbId),
    unmatched: outcome.unmatched,
  });
  await writeJson(join(dir, CATALOG_FILE), catalog);
  return catalog;
};
