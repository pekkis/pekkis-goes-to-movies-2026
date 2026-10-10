import { parseArgs } from "node:util";
import { createDb } from "../db/database.ts";
import { createMigrator, report } from "../db/migrate.ts";
import { loadEnv } from "../lib/env.ts";

const { values } = parseArgs({
  options: {
    down: { type: "boolean", default: false },
    test: { type: "boolean", default: false },
  },
});

const env = loadEnv();
const url = values.test ? env.TEST_DATABASE_URL : env.DATABASE_URL;
if (!url) throw new Error("TEST_DATABASE_URL is not set (check .env)");

const db = createDb(url);
try {
  const migrator = createMigrator(db);
  console.log(values.down ? "migrating one step down" : "migrating to latest");
  report(values.down ? await migrator.migrateDown() : await migrator.migrateToLatest());
} finally {
  await db.destroy();
}
