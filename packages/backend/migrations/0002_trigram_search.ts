import { sql, type Kysely } from "kysely";

/** Trigram similarity for fuzzy title search (`word_similarity`), used by `pnpm showtimes`. */

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function up(db: Kysely<any>): Promise<void> {
  await sql`create extension if not exists pg_trgm`.execute(db);
}

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export async function down(db: Kysely<any>): Promise<void> {
  await sql`drop extension if exists pg_trgm`.execute(db);
}
