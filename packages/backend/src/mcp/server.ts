import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { Kysely } from "kysely";
import { z } from "zod";
import type { Screening } from "../api/schemas.ts";
import type { DB } from "../db/types.ts";
import { searchFilmSummaries } from "../queries/films.ts";
import { listScreenings } from "../queries/screenings.ts";
import { listVenues } from "../queries/venues.ts";
import { helsinkiToday } from "../search/showtimes.ts";

/**
 * MCP server for chatbots: the same read-only data as the HTTP API, as three tools a model
 * can call. Results are compact JSON with the cinemas' own ticket links. Critics' scores
 * only when asked for (`include_ratings`): some people don't want verdicts beforehand.
 */
export const ATTRIBUTION =
  "Showtimes come from each cinema; every ticket link goes to the cinema's own page. " +
  "Film data from TMDB (this product uses the TMDB API but is not endorsed or certified by " +
  "TMDB). Venue coordinates partly © OpenStreetMap contributors (ODbL). Some showtimes " +
  "from the City of Helsinki's Linked Events API (CC BY 4.0).";

const INSTRUCTIONS =
  "Showtimes of Finnish cinemas. Times are Helsinki local time; a programme day runs into " +
  "the night (a 00:30 show belongs to the evening before). Use find_film to turn a film " +
  "name into an id, whats_on for screenings by place, time and film, list_venues for " +
  "cinemas. Always give the user the ticket_url of a screening they are interested in. " +
  "Do not mention critics' scores unless the user asks for them. " +
  ATTRIBUTION;

const MAX_RESULTS = 100;

const time = z
  .string()
  .regex(/^([01]\d|2[0-3]):[0-5]\d$/)
  .describe("HH:MM, Helsinki time");

/** Minutes into the programme day, which starts at 05:00, so 00:30 sorts after 23:00. */
const programmeMinutes = (hhmm: string): number => {
  const [h, m] = hhmm.split(":").map(Number) as [number, number];
  return (h * 60 + m - 5 * 60 + 24 * 60) % (24 * 60);
};

const distanceKm = (a: { lat: number; lon: number }, b: { lat: number; lon: number }) => {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLon = (b.lon - a.lon) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
};

type ScreeningOut = z.infer<typeof Screening>;

const compactScreening = (
  s: ScreeningOut,
  includeRatings: boolean,
  near?: { lat: number; lon: number },
) => ({
  date: s.businessDate,
  time: s.startsAt.slice(11, 16),
  starts_at: s.startsAt,
  film: {
    id: s.film.id,
    title: s.film.title,
    ...(s.film.originalTitle && { original_title: s.film.originalTitle }),
    ...(s.film.rating && { age_rating: s.film.rating }),
    ...(s.film.isEvent && { event: true }),
    ...(includeRatings &&
      s.film.ratings.length > 0 && {
        ratings: s.film.ratings.map((r) => `${r.source}: ${r.display}`),
      }),
  },
  venue: { id: s.venue.id, name: s.venue.name, city: s.venue.city },
  ...(near && s.venue.geo && { distance_km: Math.round(distanceKm(near, s.venue.geo) * 10) / 10 }),
  ...(s.auditorium && { hall: s.auditorium }),
  ...(s.audio.length > 0 && { audio: s.audio }),
  ...(s.dubbed !== null && { dubbed: s.dubbed }),
  subtitles: s.subtitles.kind === "languages" ? s.subtitles.languages : s.subtitles.kind,
  ...(s.tags.length > 0 && { tags: s.tags }),
  ...(s.series.length > 0 && { series: s.series }),
  availability: s.availability,
  ...(s.price && { price: `${(s.price.amountCents / 100).toFixed(2)} ${s.price.currency}` }),
  ...(s.ticketUrl && { ticket_url: s.ticketUrl }),
});

const json = (value: unknown) => ({
  content: [{ type: "text" as const, text: JSON.stringify(value) }],
});

/** A fresh server per request: stateless, so any number of chatbots can call at once. */
export const createMcpServer = (db: Kysely<DB>): McpServer => {
  const server = new McpServer(
    { name: "pekkis-goes-to-movies", version: "1.0.0" },
    { instructions: INSTRUCTIONS },
  );

  server.registerTool(
    "find_film",
    {
      title: "Find a film",
      description:
        "Fuzzy-search films showing in Finnish cinemas by any title (Finnish, Swedish, " +
        "English, original); typos are fine. Returns film ids for whats_on.",
      inputSchema: {
        query: z.string().min(2).describe("Film name, e.g. 'odysseia' or 'Kerro kaikille'"),
        include_ratings: z.boolean().default(false).describe("Add critics' scores"),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async ({ query, include_ratings }) => {
      const hits = await searchFilmSummaries(db, query, 8);
      return json({
        films: hits.map(({ film }) => ({
          id: film.id,
          title: film.title,
          ...(film.originalTitle && { original_title: film.originalTitle }),
          ...(film.year && { year: film.year }),
          ...(film.runtimeMinutes && { runtime_minutes: film.runtimeMinutes }),
          ...(film.rating && { age_rating: film.rating }),
          ...(film.isEvent && { event: true }),
          ...(include_ratings && {
            ratings: film.ratings.map((r) => `${r.source}: ${r.display}`),
          }),
        })),
      });
    },
  );

  server.registerTool(
    "whats_on",
    {
      title: "What's on",
      description:
        "Screenings on one programme day, in start order, filtered by city or position, " +
        "time window and film. Each has the cinema's own ticket link.",
      inputSchema: {
        date: z.iso.date().optional().describe("YYYY-MM-DD; default today in Helsinki"),
        city: z.string().optional().describe("City, e.g. 'Tampere'"),
        near: z
          .object({
            lat: z.number().min(59).max(71),
            lon: z.number().min(19).max(32),
            radius_km: z.number().positive().max(300).default(15),
          })
          .optional()
          .describe("Only cinemas within radius_km of a point; adds distance_km"),
        after: time.optional().describe("Only shows starting at or after this time"),
        before: time
          .optional()
          .describe("Only shows starting before this time (05:00 counts as day start)"),
        film_id: z.string().optional().describe("From find_film, e.g. 'tmdb:1368337'"),
        venue_id: z.string().optional().describe("From list_venues"),
        include_ratings: z.boolean().default(false).describe("Add critics' scores"),
        limit: z.number().int().min(1).max(MAX_RESULTS).default(40),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async (args) => {
      const date = args.date ?? (await helsinkiToday(db));
      const near = args.near;
      const latSpan = near ? near.radius_km / 111 : 0;
      const lonSpan = near ? near.radius_km / (111 * Math.cos((near.lat * Math.PI) / 180)) : 0;
      const page = await listScreenings(db, {
        date,
        ...(args.city && { city: args.city }),
        ...(near && {
          bbox: {
            minLat: near.lat - latSpan,
            maxLat: near.lat + latSpan,
            minLon: near.lon - lonSpan,
            maxLon: near.lon + lonSpan,
          },
        }),
        ...(args.film_id && { filmId: args.film_id }),
        ...(args.venue_id && { venueId: args.venue_id }),
        ...(args.after && { after: args.after }),
        limit: 2000,
      });
      const before = args.before ? programmeMinutes(args.before) : undefined;
      const matching = page.items.filter(
        (s) =>
          (before === undefined || programmeMinutes(s.startsAt.slice(11, 16)) < before) &&
          (!near || !s.venue.geo || distanceKm(near, s.venue.geo) <= near.radius_km),
      );
      return json({
        date,
        count: matching.length,
        ...(matching.length > args.limit && {
          note: `Showing the first ${args.limit}; narrow the search or raise limit.`,
        }),
        screenings: matching
          .slice(0, args.limit)
          .map((s) => compactScreening(s, args.include_ratings, near)),
      });
    },
  );

  server.registerTool(
    "list_venues",
    {
      title: "List cinemas",
      description: "Cinemas we have showtimes for, optionally in one city.",
      inputSchema: { city: z.string().optional().describe("City, e.g. 'Helsinki'") },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async ({ city }) => {
      const venues = await listVenues(db, city ? { city } : {});
      return json({
        venues: venues.map((v) => ({
          id: v.id,
          name: v.name,
          city: v.city,
          ...(v.address && { address: v.address }),
          ...(v.url && { website: v.url }),
        })),
      });
    },
  );

  return server;
};
