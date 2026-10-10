import { promises as fs } from "node:fs";
import path from "node:path";
import type { Kysely } from "kysely";
import { FileMigrationProvider, Migrator, type MigrationResultSet } from "kysely/migration";
import { MIGRATIONS_DIR } from "../lib/paths.ts";

// oxlint-disable-next-line typescript/no-explicit-any -- migrations work on any schema version
export const createMigrator = (db: Kysely<any>): Migrator =>
  new Migrator({
    db,
    provider: new FileMigrationProvider({ fs, path, migrationFolder: MIGRATIONS_DIR }),
  });

/** Throws on failure, after reporting which migration failed. */
export const report = ({ error, results }: MigrationResultSet): void => {
  for (const r of results ?? []) {
    console.log(
      `  ${r.status === "Success" ? "ok  " : r.status === "Error" ? "FAIL" : "skip"} ${r.direction.toLowerCase()} ${r.migrationName}`,
    );
  }
  if (error) throw error instanceof Error ? error : new Error(String(error));
  if (!results?.length) console.log("  nothing to do");
};
