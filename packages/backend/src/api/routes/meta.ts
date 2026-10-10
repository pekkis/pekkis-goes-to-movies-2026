import { createRoute } from "@hono/zod-openapi";
import { router } from "../hono.ts";
import { sql, type Kysely } from "kysely";
import type { DB } from "../../db/types.ts";
import { Health } from "../schemas.ts";

const health = createRoute({
  method: "get",
  path: "/v1/health",
  tags: ["meta"],
  summary: "Liveness and database check",
  responses: {
    200: { description: "Up", content: { "application/json": { schema: Health } } },
    503: {
      description: "Database unreachable",
      content: { "application/json": { schema: Health } },
    },
  },
});

export const metaRoutes = (db: Kysely<DB>) =>
  router().openapi(health, async (c) => {
    c.header("cache-control", "no-store");
    try {
      await sql`select 1`.execute(db);
      return c.json({ ok: true, db: true }, 200);
    } catch {
      return c.json({ ok: false, db: false }, 503);
    }
  });
