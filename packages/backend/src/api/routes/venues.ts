import { createRoute, z } from "@hono/zod-openapi";
import { router } from "../hono.ts";
import type { Kysely } from "kysely";
import type { DB } from "../../db/types.ts";
import { getVenue, listVenues } from "../../queries/venues.ts";
import { bboxParam, idParam, parseBbox } from "../params.ts";
import { ErrorBody, Venue } from "../schemas.ts";

const list = createRoute({
  method: "get",
  path: "/v1/venues",
  tags: ["venues"],
  summary: "Venues, optionally inside a map viewport",
  request: {
    query: z.object({
      bbox: bboxParam,
      city: z.string().optional().openapi({ example: "Jyväskylä" }),
    }),
  },
  responses: {
    200: { description: "Venues", content: { "application/json": { schema: z.array(Venue) } } },
    400: { description: "Bad parameters", content: { "application/json": { schema: ErrorBody } } },
  },
});

const one = createRoute({
  method: "get",
  path: "/v1/venues/{id}",
  tags: ["venues"],
  summary: "One venue",
  request: { params: idParam("kinoaurora:venue:jyvaskyla") },
  responses: {
    200: { description: "The venue", content: { "application/json": { schema: Venue } } },
    404: { description: "No such venue", content: { "application/json": { schema: ErrorBody } } },
  },
});

export const venueRoutes = (db: Kysely<DB>) =>
  router()
    .openapi(list, async (c) => {
      const { bbox, city } = c.req.valid("query");
      return c.json(await listVenues(db, { bbox: bbox ? parseBbox(bbox) : undefined, city }), 200);
    })
    .openapi(one, async (c) => {
      const venue = await getVenue(db, c.req.valid("param").id);
      return venue ? c.json(venue, 200) : c.json({ error: "venue not found" }, 404);
    });
