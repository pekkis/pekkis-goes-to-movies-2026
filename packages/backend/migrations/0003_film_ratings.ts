import { sql, type Kysely } from "kysely";

/**
 * Critics' and audience scores per film and source (TMDB; Rotten Tomatoes, Metacritic and
 * IMDb via OMDb). A snapshot: ingest replaces a film's ratings with the latest fetch.
 */

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function up(db: Kysely<any>): Promise<void> {
  await db.schema
    .createTable("film_ratings")
    .addColumn("film_id", "text", (c) => c.notNull().references("films.id").onDelete("cascade"))
    .addColumn("source", "text", (c) => c.notNull())
    .addColumn("score", "smallint", (c) => c.notNull().check(sql`score between 0 and 100`))
    .addColumn("display", "text", (c) => c.notNull())
    .addColumn("votes", "integer")
    .addColumn("fetched_at", "timestamptz", (c) => c.notNull())
    .addColumn("created_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addColumn("updated_at", "timestamptz", (c) => c.notNull().defaultTo(sql`now()`))
    .addPrimaryKeyConstraint("film_ratings_pkey", ["film_id", "source"])
    .execute();
  await db.schema
    .createIndex("film_ratings_source_score_idx")
    .on("film_ratings")
    .columns(["source", "score"])
    .execute();
}

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function down(db: Kysely<any>): Promise<void> {
  await db.schema.dropTable("film_ratings").execute();
}
