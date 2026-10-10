import { CamelCasePlugin, Kysely, PostgresDialect } from "kysely";
import pg from "pg";
import type { DB } from "./types.ts";

// `date` columns stay "YYYY-MM-DD" strings, as in the model (pg would make them local-midnight Dates).
pg.types.setTypeParser(pg.types.builtins.DATE, (value) => value);

/**
 * TypeScript uses the model's camelCase (`startsAt`); the database is snake_case
 * (`starts_at`). CamelCasePlugin translates both ways, so nothing is mapped by hand.
 */
export const createDb = (connectionString: string): Kysely<DB> =>
  new Kysely<DB>({
    dialect: new PostgresDialect({ pool: new pg.Pool({ connectionString, max: 5 }) }),
    plugins: [new CamelCasePlugin()],
  });
