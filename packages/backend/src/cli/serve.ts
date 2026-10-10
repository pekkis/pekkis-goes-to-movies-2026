import { serve } from "@hono/node-server";
import { createApp } from "../api/app.ts";
import { createDb } from "../db/database.ts";
import { loadEnv } from "../lib/env.ts";

const env = loadEnv();
const db = createDb(env.DATABASE_URL);
const app = createApp({ db, corsOrigins: env.CORS_ORIGINS, log: true });

const server = serve({ fetch: app.fetch, port: env.PORT, hostname: env.HOST }, (info) => {
  console.log(`API listening on http://${info.address}:${info.port} (docs: /docs)`);
});

// Docker sends SIGTERM on stop: finish in-flight requests, then close the pool.
const shutdown = (signal: string) => {
  console.log(`${signal}: shutting down`);
  server.close(() => {
    void db.destroy().then(() => process.exit(0));
  });
  setTimeout(() => process.exit(1), 10_000).unref();
};
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
