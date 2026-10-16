import { sql, type Kysely } from "kysely";

/**
 * Raw labels and the series catalogue (docs/classification.md).
 * `screenings.labels`: every label the source printed, verbatim, as [{ source, text }].
 * `series`: the strands, festivals, clubs and other series that `screenings.series` ids
 * point to: registry ids ("kuvi-aluesarja") and provider strands ("kinoregina/teema").
 * Rows ingested before this keep display names in `screenings.series`.
 */

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function up(db: Kysely<any>): Promise<void> {
  await db.schema
    .alterTable("screenings")
    .addColumn("labels", "jsonb", (c) => c.notNull().defaultTo(sql`'[]'::jsonb`))
    .execute();
  await db.schema
    .createTable("series")
    .addColumn("id", "text", (c) => c.primaryKey())
    .addColumn("name", "text", (c) => c.notNull())
    .addColumn("kind", "text", (c) => c.notNull())
    .addColumn("created_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addColumn("updated_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .execute();
}

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function down(db: Kysely<any>): Promise<void> {
  await db.schema.dropTable("series").execute();
  await db.schema.alterTable("screenings").dropColumn("labels").execute();
}
