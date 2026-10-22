import { Scalar } from "@scalar/hono-api-reference";
import type { Kysely } from "kysely";
import { cors } from "hono/cors";
import { logger } from "hono/logger";
import { secureHeaders } from "hono/secure-headers";
import type { DB } from "../db/types.ts";
import { StreamableHTTPTransport } from "@hono/mcp";
import { createMcpServer } from "../mcp/server.ts";
import { router } from "./hono.ts";
import { filmRoutes } from "./routes/films.ts";
import { metaRoutes } from "./routes/meta.ts";
import { screeningRoutes } from "./routes/screenings.ts";
import { seriesRoutes } from "./routes/series.ts";
import { venueRoutes } from "./routes/venues.ts";

export type AppOptions = {
  db: Kysely<DB>;
  /** "*" or a list of allowed origins. */
  corsOrigins?: string | string[];
  /** Serves the MCP endpoint at `/mcp/{mcpToken}` when set (see src/mcp/server.ts). */
  mcpToken?: string | undefined;
  log?: boolean;
};

const ATTRIBUTION =
  "Showtimes come from each cinema; every ticket link goes to the cinema's own page. " +
  "Film data and images from TMDB (this product uses the TMDB API but is not endorsed or " +
  "certified by TMDB). Venue coordinates partly © OpenStreetMap contributors (ODbL). " +
  "Some showtimes from the Linked Events APIs of the Cities of Helsinki and Espoo (CC BY 4.0).";

/** The whole API. Pure wiring: no listening, so tests call `app.request()` directly. */
export const createApp = ({ db, corsOrigins = "*", log = false, mcpToken }: AppOptions) => {
  const app = router();
  if (log) {
    // The MCP token is in the path: keep it out of the logs.
    const redact = (line: string) => (mcpToken ? line.replaceAll(mcpToken, "…") : line);
    app.use(logger((line, ...rest) => console.log(redact(line), ...rest)));
  }
  app.use(secureHeaders());
  app.use("/v1/*", cors({ origin: corsOrigins, allowMethods: ["GET", "HEAD", "OPTIONS"] }));
  app.use("/v1/*", async (c, next) => {
    await next();
    if (c.res.status === 200 && !c.res.headers.has("cache-control")) {
      c.header("cache-control", "public, max-age=60");
    }
  });

  const api = app
    .route("/", metaRoutes(db))
    .route("/", venueRoutes(db))
    .route("/", screeningRoutes(db))
    .route("/", filmRoutes(db))
    .route("/", seriesRoutes(db));

  if (mcpToken) {
    // Stateless (no session id generator): a fresh server and transport per request.
    app.all(`/mcp/${mcpToken}`, async (c) => {
      // GET would open a stream for server-sent messages, which a stateless server never
      // sends: it would just hang (in a browser, forever). The spec lets servers answer 405.
      if (c.req.method !== "POST") {
        c.header("allow", "POST");
        return c.json({ error: "MCP over Streamable HTTP: POST JSON-RPC here" }, 405);
      }
      const server = createMcpServer(db);
      const transport = new StreamableHTTPTransport();
      await server.connect(transport);
      return transport.handleRequest(c);
    });
  }

  api.doc31("/openapi.json", {
    openapi: "3.1.0",
    info: {
      title: "Pekkis goes to movies API",
      version: "1.0.0",
      description: `Showtimes of Finnish cinemas. Read-only, no authentication.\n\n${ATTRIBUTION}`,
      license: { name: "AGPL-3.0-or-later", url: "https://www.gnu.org/licenses/agpl-3.0.html" },
    },
  });
  api.get("/docs", Scalar({ url: "/openapi.json", pageTitle: "Pekkis goes to movies API" }));
  api.notFound((c) => c.json({ error: "not found" }, 404));
  api.onError((error, c) => {
    console.error(error);
    return c.json({ error: "internal error" }, 500);
  });
  return api;
};

/** For typed clients: `hc<AppType>(baseUrl)` from `hono/client`. */
export type AppType = ReturnType<typeof createApp>;
