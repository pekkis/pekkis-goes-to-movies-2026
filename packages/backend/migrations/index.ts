import type { Migration } from "kysely/migration";
import * as m0001 from "./0001_initial.ts";
import * as m0002 from "./0002_trigram_search.ts";

/**
 * Every migration, by name, in order. Imported statically so the API bundle (tsdown)
 * carries them; a file-system scan would look for .ts files next to the bundle.
 * Add each new migration here (test/migrations.test.ts fails if one is missing).
 */
export const MIGRATIONS: Record<string, Migration> = {
  "0001_initial": m0001,
  "0002_trigram_search": m0002,
};
