import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { loadEnv } from "../lib/env.ts";

/**
 * Regenerates src/db/types.ts from the migrated development database.
 * Run after every migration: `pnpm migrate && pnpm db:types`. Never edit types.ts by hand.
 */
const { DATABASE_URL } = loadEnv();
const outFile = fileURLToPath(new URL("../db/types.ts", import.meta.url));

execFileSync(
  "kysely-codegen",
  [
    "--dialect=postgres",
    "--camel-case",
    "--date-parser=string",
    `--out-file=${outFile}`,
    "--exclude-pattern=kysely_*",
    ...process.argv.slice(2),
  ],
  { stdio: "inherit", env: { ...process.env, DATABASE_URL } },
);
