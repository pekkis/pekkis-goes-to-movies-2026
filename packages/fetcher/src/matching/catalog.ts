import { readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { FilmCatalog, ProviderBatch, type Film } from "@pgtm/model";
import type { TmdbClient } from "../tmdb/client.ts";
import type { Aliases } from "./aliases.ts";
import { matchListings } from "./match.ts";

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
  );

  for (const { file, batch } of batches) {
    const listings = batch.listings.map(({ filmId: _f, match: _m, ...listing }) => {
      const link = outcome.links.get(listing.id);
      return link ? { ...listing, filmId: link.filmId, match: link.method } : listing;
    });
    const screenings = batch.screenings.map(({ filmId: _f, ...screening }) => {
      const link = outcome.links.get(screening.listingId);
      return link ? { ...screening, filmId: link.filmId } : screening;
    });
    await writeJson(join(dir, file), ProviderBatch.parse({ ...batch, listings, screenings }));
  }

  const catalog = FilmCatalog.parse({
    generatedAt: now.toISOString(),
    films: (await enrich(outcome.films)).sort((a, b) => a.tmdbId - b.tmdbId),
    unmatched: outcome.unmatched,
  });
  await writeJson(join(dir, CATALOG_FILE), catalog);
  return catalog;
};
