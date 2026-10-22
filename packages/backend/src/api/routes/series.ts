import { createRoute, z } from "@hono/zod-openapi";
import { addDays, daysBetween } from "@pgtm/model/time";
import type { Kysely } from "kysely";
import type { DB } from "../../db/types.ts";
import { listSeries } from "../../queries/series.ts";
import { helsinkiToday } from "../../search/showtimes.ts";
import { router } from "../hono.ts";
import { MAX_TEXT } from "../params.ts";
import { ErrorBody, Series } from "../schemas.ts";

const SERIES_MAX_DAYS = 62;

const list = createRoute({
  method: "get",
  path: "/v1/series",
  tags: ["series"],
  summary:
    "Series with screenings between two days: cinemas' strands, festivals, clubs, distributors' series",
  request: {
    query: z.object({
      from: z.iso
        .date()
        .optional()
        .openapi({ description: "Default: today.", example: "2026-10-22" }),
      to: z.iso
        .date()
        .optional()
        .openapi({
          description: `Default: 27 days after from; at most ${SERIES_MAX_DAYS} days.`,
          example: "2026-11-18",
        }),
      q: z
        .string()
        .trim()
        .min(2)
        .max(MAX_TEXT)
        .optional()
        .openapi({ description: "Part of the name or id, case-insensitive.", example: "suleiman" }),
    }),
  },
  responses: {
    200: {
      description: "Series, most screenings first",
      content: { "application/json": { schema: z.array(Series) } },
    },
    400: { description: "Bad parameters", content: { "application/json": { schema: ErrorBody } } },
  },
});

export const seriesRoutes = (db: Kysely<DB>) =>
  router().openapi(list, async (c) => {
    const q = c.req.valid("query");
    const from = q.from ?? (await helsinkiToday(db));
    const to = q.to ?? addDays(from, 27);
    const span = daysBetween(from, to);
    if (span < 0 || span > SERIES_MAX_DAYS) {
      return c.json({ error: `from must not be after to, at most ${SERIES_MAX_DAYS} days` }, 400);
    }
    return c.json(await listSeries(db, from, to, q.q), 200);
  });
