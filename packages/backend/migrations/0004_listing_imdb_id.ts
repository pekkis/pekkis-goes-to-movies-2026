import type { Kysely } from "kysely";

/** The provider's IMDb id for a listing (Kinola, Johku), which matching looks up on TMDB. */

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function up(db: Kysely<any>): Promise<void> {
  await db.schema.alterTable("film_listings").addColumn("imdb_id", "text").execute();
}

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function down(db: Kysely<any>): Promise<void> {
  await db.schema.alterTable("film_listings").dropColumn("imdb_id").execute();
}
