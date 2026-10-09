import { join } from "node:path";
import { createDiskCache } from "../lib/cache.ts";
import { createTmdbClient, createTmdbHttp } from "../tmdb/client.ts";
import type { Env } from "../lib/env.ts";
import { loadAliases } from "./aliases.ts";
import { buildCatalog } from "./catalog.ts";

/** Matches all normalized batches under `{out}/normalized` and prints what stayed unmatched. */
export const runMatching = async (out: string, env: Env) => {
  const tmdb = createTmdbClient(
    createTmdbHttp(env.TMDB_APIKEY, env.CONTACT),
    createDiskCache(join(out, "cache", "tmdb")),
  );
  const catalog = await buildCatalog(join(out, "normalized"), tmdb, await loadAliases());
  console.log(`tmdb: ${catalog.films.length} films, ${catalog.unmatched.length} unmatched`);
  for (const u of catalog.unmatched) {
    console.log(`  ${u.listingId} "${u.title}": ${u.reason}`);
    for (const c of u.candidates.slice(0, 3)) {
      console.log(`      ? ${c.tmdbId} "${c.title}" ${c.year ?? ""}`);
    }
  }
  if (catalog.unmatched.length) console.log("  -> add aliases to config/tmdb-aliases.json");
};
