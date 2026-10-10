import { sql } from "kysely";
import { createDb } from "../src/db/database.ts";
import { createMigrator, report } from "../src/db/migrate.ts";

/** Recreates the test database schema from the migrations before the test run. */
export default async function setup(): Promise<void> {
  const url = process.env["TEST_DATABASE_URL"];
  if (!url) {
    throw new Error("TEST_DATABASE_URL is not set. Run `pnpm db:up` and see .env.example.");
  }
  const db = createDb(url);
  try {
    await sql`drop schema if exists public cascade`.execute(db);
    await sql`create schema public`.execute(db);
    report(await createMigrator(db).migrateToLatest());
  } finally {
    await db.destroy();
  }
}
