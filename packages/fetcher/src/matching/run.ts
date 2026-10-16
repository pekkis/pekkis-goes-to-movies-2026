import { join } from "node:path";
import { createDiskCache } from "../lib/cache.ts";
import { createHttpClient } from "../lib/http.ts";
import { paintFor } from "../lib/paint.ts";
import { addOmdbRatings, fetchOmdb } from "../ratings/omdb.ts";
import { createTmdbClient, createTmdbHttp } from "../tmdb/client.ts";
import { requireTmdbKey, type Env } from "../lib/env.ts";
import { loadAliases } from "./aliases.ts";
import { buildCatalog } from "./catalog.ts";

/** Matches all normalized batches under `{out}/normalized` and prints what stayed unmatched. */
export const runMatching = async (out: string, env: Env) => {
  const tmdb = createTmdbClient(
    createTmdbHttp(requireTmdbKey(env), env.CONTACT),
    createDiskCache(join(out, "cache", "tmdb")),
  );
  const omdbKey = env.OMDB_APIKEY;
  const omdbHttp = createHttpClient({
    intervalMs: 250,
    ...(env.CONTACT && { contact: env.CONTACT }),
  });
  const omdbCache = createDiskCache(join(out, "cache", "omdb"));
  const paint = paintFor(process.stdout);
  let ratingsNote = "ratings: TMDB only (set OMDB_APIKEY for Rotten Tomatoes, Metacritic, IMDb)";
  const enrich = async (films: Parameters<typeof addOmdbRatings>[0]) => {
    if (!omdbKey) {
      return films;
    }
    const result = await addOmdbRatings(films, (imdbId) =>
      fetchOmdb(omdbHttp, omdbCache, omdbKey, imdbId),
    );
    ratingsNote = `omdb: ratings for ${result.rated} of ${films.length} films`;
    if (result.error) {
      ratingsNote += ` ${paint("red", `(stopped: ${result.error})`)}`;
    }
    return result.films;
  };

  const catalog = await buildCatalog(
    join(out, "normalized"),
    tmdb,
    await loadAliases(),
    new Date(),
    enrich,
  );
  const unmatched = `${catalog.unmatched.length} unmatched`;
  console.log(
    `${paint("bold", "tmdb")}: ${catalog.films.length} films, ${catalog.unmatched.length ? paint("yellow", unmatched) : unmatched}`,
  );
  console.log(ratingsNote);
  for (const u of catalog.unmatched) {
    console.log(`  ${u.listingId} ${paint("bold", `"${u.title}"`)}: ${paint("yellow", u.reason)}`);
    for (const c of u.candidates.slice(0, 3)) {
      console.log(`      ? ${c.tmdbId} "${c.title}" ${c.year ?? ""}`);
    }
  }
  if (catalog.unmatched.length) {
    console.log(paint("cyan", "  -> add aliases to config/tmdb-aliases.json"));
  }
};
