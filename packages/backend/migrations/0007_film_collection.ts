import type { Kysely } from "kysely";

/** The film series a film belongs to (TMDB collection), for "follow a film series". */

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function up(db: Kysely<any>): Promise<void> {
  await db.schema
    .alterTable("films")
    .addColumn("collection_tmdb_id", "integer")
    .addColumn("collection_name", "text")
    .execute();
}

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function down(db: Kysely<any>): Promise<void> {
  await db.schema
    .alterTable("films")
    .dropColumn("collection_tmdb_id")
    .dropColumn("collection_name")
    .execute();
}
