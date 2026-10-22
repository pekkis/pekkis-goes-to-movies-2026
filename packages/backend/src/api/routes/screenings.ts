import { createRoute, z } from "@hono/zod-openapi";
import { router } from "../hono.ts";
import type { Kysely } from "kysely";
import type { DB } from "../../db/types.ts";
import { decodeCursor, encodeCursor, listScreenings } from "../../queries/screenings.ts";
import { helsinkiToday } from "../../search/showtimes.ts";
import {
  afterParam,
  bboxParam,
  dateParam,
  limitParam,
  MAX_ID,
  MAX_TEXT,
  parseBbox,
} from "../params.ts";
import { ErrorBody, ScreeningPage } from "../schemas.ts";
import { ScreeningTag } from "@pgtm/model";
import { daysBetween } from "@pgtm/model/time";

/** The longest span one request covers. */
const MAX_SPAN_DAYS = 31;

const list = createRoute({
  method: "get",
  path: "/v1/screenings",
  tags: ["screenings"],
  summary: "What's on: screenings of one day, by place, time, venue or film",
  request: {
    query: z.object({
      date: dateParam,
      bbox: bboxParam,
      city: z
        .string()
        .min(1)
        .max(MAX_TEXT)
        .optional()
        .openapi({ description: "Venue city, case-insensitive.", example: "Tampere" }),
      venue: z.string().max(MAX_ID).optional().openapi({ description: "Venue id." }),
      film: z
        .string()
        .max(MAX_ID)
        .optional()
        .openapi({ description: "Film id (tmdb:…) or listing id." }),
      to: z.iso
        .date()
        .optional()
        .openapi({
          description: `The last business date, for a span of days (at most ${MAX_SPAN_DAYS} after date).`,
          example: "2026-11-18",
        }),
      tags: z
        .string()
        .max(MAX_ID)
        .optional()
        .transform((v) => (v ? v.split(",").map((t) => t.trim()) : []))
        .pipe(z.array(z.enum(ScreeningTag.options)))
        .openapi({
          type: "string",
          description: "Comma-separated screening tags; with series, any of them matches.",
          example: "classic,domestic",
        }),
      series: z
        .string()
        .max(MAX_ID * 4)
        .optional()
        .transform((v) =>
          v
            ? v
                .split(",")
                .map((t) => t.trim())
                .filter(Boolean)
            : [],
        )
        .openapi({
          type: "string",
          description:
            "Comma-separated series ids, from /v1/series; with tags, any of them matches.",
          example: "neulekino,kirjastokino",
        }),
      after: afterParam,
      limit: limitParam(500, 2000),
      cursor: z
        .string()
        .max(MAX_ID)
        .optional()
        .openapi({ description: "`nextCursor` of the previous page." }),
    }),
  },
  responses: {
    200: {
      description: "One page of screenings",
      content: { "application/json": { schema: ScreeningPage } },
    },
    400: { description: "Bad parameters", content: { "application/json": { schema: ErrorBody } } },
  },
});

export const screeningRoutes = (db: Kysely<DB>) =>
  router().openapi(list, async (c) => {
    const q = c.req.valid("query");
    const cursor = q.cursor === undefined ? undefined : decodeCursor(q.cursor);
    if (q.cursor !== undefined && !cursor) {
      return c.json({ error: "invalid cursor" }, 400);
    }
    const date = q.date ?? (await helsinkiToday(db));
    if (q.to !== undefined) {
      const span = daysBetween(date, q.to);
      if (span < 0 || span > MAX_SPAN_DAYS) {
        return c.json({ error: `to must be from date up to ${MAX_SPAN_DAYS} days after it` }, 400);
      }
    }
    const page = await listScreenings(db, {
      date,
      bbox: q.bbox ? parseBbox(q.bbox) : undefined,
      city: q.city,
      venueId: q.venue,
      filmId: q.film,
      to: q.to,
      tags: q.tags,
      seriesIds: q.series,
      after: q.after,
      limit: q.limit,
      cursor,
    });
    return c.json(
      { date, items: page.items, nextCursor: page.nextCursor && encodeCursor(page.nextCursor) },
      200,
    );
  });
