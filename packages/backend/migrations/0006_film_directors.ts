import { sql, type Kysely } from "kysely";

/** A film's directors from TMDB credits: `[{ tmdbId, name }]`, for "follow a director". */

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function up(db: Kysely<any>): Promise<void> {
  await db.schema
    .alterTable("films")
    .addColumn("directors", "jsonb", (c) => c.notNull().defaultTo(sql`'[]'::jsonb`))
    .execute();
}

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function down(db: Kysely<any>): Promise<void> {
  await db.schema.alterTable("films").dropColumn("directors").execute();
}
