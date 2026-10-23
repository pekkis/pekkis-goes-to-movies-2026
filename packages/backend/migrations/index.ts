import type { Migration } from "kysely/migration";
import * as m0001 from "./0001_initial.ts";
import * as m0002 from "./0002_trigram_search.ts";
import * as m0003 from "./0003_film_ratings.ts";
import * as m0004 from "./0004_listing_imdb_id.ts";
import * as m0005 from "./0005_labels_series.ts";
import * as m0006 from "./0006_film_directors.ts";
import * as m0007 from "./0007_film_collection.ts";
import * as m0008 from "./0008_venue_checks.ts";

/**
 * Every migration, by name, in order. Imported statically so the API bundle (tsdown)
 * carries them; a file-system scan would look for .ts files next to the bundle.
 * Add each new migration here (test/migrations.test.ts fails if one is missing).
 */
export const MIGRATIONS: Record<string, Migration> = {
  "0001_initial": m0001,
  "0002_trigram_search": m0002,
  "0003_film_ratings": m0003,
  "0004_listing_imdb_id": m0004,
  "0005_labels_series": m0005,
  "0006_film_directors": m0006,
  "0007_film_collection": m0007,
  "0008_venue_checks": m0008,
};
