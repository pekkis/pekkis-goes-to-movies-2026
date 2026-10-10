import { createRoute, z } from "@hono/zod-openapi";
import { router } from "../hono.ts";
import type { Kysely } from "kysely";
import type { DB } from "../../db/types.ts";
import { getFilm, searchFilmSummaries } from "../../queries/films.ts";
import { listScreenings } from "../../queries/screenings.ts";
import { helsinkiToday } from "../../search/showtimes.ts";
import { afterParam, bboxParam, dateParam, idParam, limitParam, parseBbox } from "../params.ts";
import { ErrorBody, Film, ScreeningPage, SearchHit } from "../schemas.ts";

const search = createRoute({
  method: "get",
  path: "/v1/films/search",
  tags: ["films"],
  summary: "Fuzzy film search by any title (Finnish, Swedish, English, original; typos allowed)",
  request: {
    query: z.object({
      q: z.string().trim().min(2).openapi({ example: "odysey" }),
      limit: limitParam(10, 50),
    }),
  },
  responses: {
    200: {
      description: "Hits, best first",
      content: { "application/json": { schema: z.array(SearchHit) } },
    },
    400: { description: "Bad parameters", content: { "application/json": { schema: ErrorBody } } },
  },
});

const one = createRoute({
  method: "get",
  path: "/v1/films/{id}",
  tags: ["films"],
  summary: "A film (TMDB) or an unmatched cinema listing",
  request: { params: idParam("tmdb:1185806") },
  responses: {
    200: { description: "The film", content: { "application/json": { schema: Film } } },
    404: { description: "No such film", content: { "application/json": { schema: ErrorBody } } },
  },
});

const screenings = createRoute({
  method: "get",
  path: "/v1/films/{id}/screenings",
  tags: ["films"],
  summary: "Where and when a film plays on one day",
  request: {
    params: idParam("tmdb:1185806"),
    query: z.object({ date: dateParam, bbox: bboxParam, after: afterParam }),
  },
  responses: {
    200: {
      description: "All of the day's screenings",
      content: { "application/json": { schema: ScreeningPage } },
    },
    400: { description: "Bad parameters", content: { "application/json": { schema: ErrorBody } } },
    404: { description: "No such film", content: { "application/json": { schema: ErrorBody } } },
  },
});

/** One film plays at most a few hundred times a day nationwide; no paging needed. */
const FILM_DAY_LIMIT = 2000;

export const filmRoutes = (db: Kysely<DB>) =>
  router()
    // Registered before /{id} so "search" is not taken for an id.
    .openapi(search, async (c) => {
      const { q, limit } = c.req.valid("query");
      return c.json(await searchFilmSummaries(db, q, limit), 200);
    })
    .openapi(one, async (c) => {
      const film = await getFilm(db, c.req.valid("param").id);
      return film ? c.json(film, 200) : c.json({ error: "film not found" }, 404);
    })
    .openapi(screenings, async (c) => {
      const { id } = c.req.valid("param");
      const q = c.req.valid("query");
      if (!(await getFilm(db, id))) return c.json({ error: "film not found" }, 404);
      const date = q.date ?? (await helsinkiToday(db));
      const page = await listScreenings(db, {
        date,
        filmId: id,
        bbox: q.bbox ? parseBbox(q.bbox) : undefined,
        after: q.after,
        limit: FILM_DAY_LIMIT,
      });
      return c.json({ date, items: page.items, nextCursor: null }, 200);
    });
