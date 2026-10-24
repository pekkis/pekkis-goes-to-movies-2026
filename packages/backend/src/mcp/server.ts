import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { Kysely } from "kysely";
import { z } from "zod";
import type { Screening } from "../api/schemas.ts";
import type { DB } from "../db/types.ts";
import { filmsPlaying, getFilm, searchFilmSummaries } from "../queries/films.ts";
import { listScreenings } from "../queries/screenings.ts";
import { listSeries } from "../queries/series.ts";
import { listVenues } from "../queries/venues.ts";
import { MAX_ID, MAX_TEXT } from "../api/params.ts";
import { helsinkiToday } from "../search/showtimes.ts";
import { distanceKm } from "@pgtm/model/geo";
import { ScreeningTag } from "@pgtm/model";
import { addDays, daysBetween } from "@pgtm/model/time";

/**
 * MCP server for chatbots: the same read-only data as the HTTP API, as six tools a model
 * can call. Results are compact JSON with the cinemas' own ticket links. Critics' scores
 * only when asked for (`include_ratings`): some people don't want verdicts beforehand.
 */
export const ATTRIBUTION =
  "Showtimes come from each cinema; every ticket link goes to the cinema's own page. " +
  "Film data from TMDB (this product uses the TMDB API but is not endorsed or certified by " +
  "TMDB). Venue coordinates partly © OpenStreetMap contributors (ODbL). Some showtimes " +
  "from the Linked Events APIs of the Cities of Helsinki and Espoo (CC BY 4.0).";

const INSTRUCTIONS =
  "Showtimes of Finnish cinemas. Times are Helsinki local time; a programme day runs into " +
  "the night (a 00:30 show belongs to the evening before). Use find_film to turn a film " +
  "name into an id, film_info for what a film is (synopsis, directors, film series), " +
  "whats_on for screenings by place, days, time, film and kind (classic, domestic, kids…), " +
  "films_playing for films over a span of days by director, film series or kind, " +
  "find_series for the cinemas' own series, festivals and clubs (a knitting screening, a " +
  "director retrospective) and their ids for whats_on and films_playing, and " +
  "list_venues for cinemas. Always give the user the ticket_url of a screening they are " +
  "interested in. " +
  "Do not mention critics' scores unless the user asks for them. " +
  ATTRIBUTION;

const MAX_RESULTS = 100;
/** Days whats_on covers at most in one call ("this weekend", "this week"). */
const MAX_DAYS = 7;
/** Days films_playing spans at most. */
const MAX_SPAN = 62;

const tag = z
  .enum(ScreeningTag.options)
  .describe(
    "A kind of screening: classic (5+ years old), domestic (made in Finland), kids, baby, " +
      "senior, premiere, preview, last-screening, event-cinema, guest, …",
  );

const time = z
  .string()
  .regex(/^([01]\d|2[0-3]):[0-5]\d$/)
  .describe("HH:MM, Helsinki time");

/** Minutes into the programme day, which starts at 05:00, so 00:30 sorts after 23:00. */
const programmeMinutes = (hhmm: string): number => {
  const [h, m] = hhmm.split(":").map(Number) as [number, number];
  return (h * 60 + m - 5 * 60 + 24 * 60) % (24 * 60);
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
        query: z
          .string()
          .min(2)
          .max(MAX_TEXT)
          .describe("Film name, e.g. 'odysseia' or 'Kerro kaikille'"),
        include_ratings: z.boolean().default(false).describe("Add critics' scores"),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async ({ query, include_ratings }) => {
      const hits = await searchFilmSummaries(db, query, 8);
      const details = await Promise.all(hits.map(({ film }) => getFilm(db, film.id)));
      return json({
        films: hits.map(({ film }, i) => ({
          id: film.id,
          title: film.title,
          ...(film.originalTitle && { original_title: film.originalTitle }),
          ...(film.year && { year: film.year }),
          ...(details[i]?.directors.length && {
            directors: details[i].directors.map((d) => d.name),
          }),
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
        "Screenings on one or more programme days, in start order, filtered by city or " +
        "position, time window, film and kind of screening. Each has the cinema's own " +
        "ticket link.",
      inputSchema: {
        date: z.iso.date().optional().describe("YYYY-MM-DD; default today in Helsinki"),
        days: z
          .number()
          .int()
          .min(1)
          .max(MAX_DAYS)
          .default(1)
          .describe("How many days from date, e.g. 3 for Friday to Sunday"),
        tag: tag.optional(),
        city: z.string().max(MAX_TEXT).optional().describe("City, e.g. 'Tampere'"),
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
        film_id: z.string().max(MAX_ID).optional().describe("From find_film, e.g. 'tmdb:1368337'"),
        venue_id: z.string().max(MAX_ID).optional().describe("From list_venues"),
        series_id: z.string().max(MAX_ID).optional().describe("From find_series"),
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
      const dates = Array.from({ length: args.days }, (_, i) => addDays(date, i));
      const pages = await Promise.all(
        dates.map((day) =>
          listScreenings(db, {
            date: day,
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
            ...(args.series_id && { seriesIds: [args.series_id] }),
            ...(args.after && { after: args.after }),
            limit: 2000,
          }),
        ),
      );
      const before = args.before ? programmeMinutes(args.before) : undefined;
      const matching = pages
        .flatMap((page) => page.items)
        .filter(
          (s) =>
            (before === undefined || programmeMinutes(s.startsAt.slice(11, 16)) < before) &&
            (!near || !s.venue.geo || distanceKm(near, s.venue.geo) <= near.radius_km) &&
            (!args.tag || s.tags.includes(args.tag)),
        );
      return json({
        date,
        ...(args.days > 1 && { to: dates.at(-1) }),
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
    "film_info",
    {
      title: "About a film",
      description:
        "What a film is: synopsis, directors, film series, genres, countries, length, age " +
        "rating, Finnish premiere and a trailer link, all from TMDB. Use the id from find_film.",
      inputSchema: {
        film_id: z.string().max(MAX_ID).describe("From find_film, e.g. 'tmdb:1368337'"),
        include_ratings: z.boolean().default(false).describe("Add critics' scores"),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async ({ film_id, include_ratings }) => {
      const film = await getFilm(db, film_id);
      if (!film) {
        return json({ error: `No film ${film_id}; use find_film for an id.` });
      }
      const trailer = film.trailers.find((t) => t.site === "YouTube");
      return json({
        id: film.id,
        title: film.title,
        ...(film.originalTitle && { original_title: film.originalTitle }),
        ...(film.year && { year: film.year }),
        ...(film.isEvent && { event: true }),
        ...(film.directors.length > 0 && { directors: film.directors.map((d) => d.name) }),
        ...(film.collection && {
          film_series: { name: film.collection.name, collection_id: film.collection.tmdbId },
        }),
        ...(film.genres.length > 0 && { genres: film.genres }),
        ...(film.countries.length > 0 && { countries: film.countries }),
        ...(film.runtimeMinutes && { runtime_minutes: film.runtimeMinutes }),
        ...(film.rating && { age_rating: film.rating }),
        ...(film.finnishReleaseDate && { finnish_premiere: film.finnishReleaseDate }),
        ...((film.overview.fi ?? film.overview.en) && {
          synopsis: film.overview.fi ?? film.overview.en,
        }),
        ...(trailer && { trailer_url: `https://www.youtube.com/watch?v=${trailer.key}` }),
        ...(include_ratings &&
          film.ratings.length > 0 && {
            ratings: film.ratings.map((r) => `${r.source}: ${r.display}`),
          }),
      });
    },
  );

  server.registerTool(
    "films_playing",
    {
      title: "Films playing",
      description:
        "Films with screenings over a span of days, each with its first day: e.g. everything " +
        "by a director, a film series, or a kind of screening (classics, domestic films) in " +
        "the coming weeks. Then use whats_on with the film_id for times and places.",
      inputSchema: {
        from: z.iso.date().optional().describe("YYYY-MM-DD; default today in Helsinki"),
        to: z.iso
          .date()
          .optional()
          .describe(`YYYY-MM-DD; default six days after from, at most ${MAX_SPAN} days`),
        director: z
          .string()
          .min(2)
          .max(MAX_TEXT)
          .optional()
          .describe("Part of a director's name, e.g. 'Bergholm'"),
        film_series: z
          .string()
          .min(2)
          .max(MAX_TEXT)
          .optional()
          .describe("Part of a film series' name, e.g. 'Niskavuori'"),
        series_id: z.string().max(MAX_ID).optional().describe("From find_series"),
        tag: tag.optional(),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async (args) => {
      const from = args.from ?? (await helsinkiToday(db));
      const to = args.to ?? addDays(from, 6);
      const span = daysBetween(from, to);
      if (span < 0 || span > MAX_SPAN) {
        return json({ error: `from must not be after to, at most ${MAX_SPAN} days` });
      }
      const films = await filmsPlaying(db, from, to, args.tag, {
        ...(args.director && { directorName: args.director }),
        ...(args.film_series && { collectionName: args.film_series }),
        ...(args.series_id && { seriesId: args.series_id }),
      });
      return json({
        from,
        to,
        count: films.length,
        films: films.slice(0, MAX_RESULTS).map(({ film, nextShowing }) => ({
          id: film.id,
          title: film.title,
          ...(film.year && { year: film.year }),
          first_day: nextShowing,
        })),
        ...(films.length === 0 && {
          note: "Only films matched to TMDB are listed; try find_film, or a longer span.",
        }),
      });
    },
  );

  server.registerTool(
    "find_series",
    {
      title: "Find a series",
      description:
        "Series with screenings in the coming weeks: cinemas' own strands (knitting " +
        "screenings, a director retrospective, Kahvikino), festivals, film clubs and " +
        "distributors' series. Without a query, the biggest ones. Returns ids for whats_on " +
        "and films_playing.",
      inputSchema: {
        query: z
          .string()
          .min(2)
          .max(MAX_TEXT)
          .optional()
          .describe("Part of the name, e.g. 'neule', 'suleiman', 'kahvi'"),
        from: z.iso.date().optional().describe("YYYY-MM-DD; default today in Helsinki"),
        to: z.iso
          .date()
          .optional()
          .describe(`YYYY-MM-DD; default 27 days after from, at most ${MAX_SPAN} days`),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async (args) => {
      const from = args.from ?? (await helsinkiToday(db));
      const to = args.to ?? addDays(from, 27);
      const span = daysBetween(from, to);
      if (span < 0 || span > MAX_SPAN) {
        return json({ error: `from must not be after to, at most ${MAX_SPAN} days` });
      }
      const series = await listSeries(db, from, to, args.query);
      return json({
        from,
        to,
        series: series.slice(0, MAX_RESULTS).map((x) => ({
          id: x.id,
          name: x.name,
          kind: x.kind,
          screenings: x.screenings,
          first_day: x.firstDay,
        })),
      });
    },
  );

  server.registerTool(
    "list_venues",
    {
      title: "List cinemas",
      description: "Cinemas we have showtimes for, optionally in one city.",
      inputSchema: { city: z.string().max(MAX_TEXT).optional().describe("City, e.g. 'Helsinki'") },
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
          ...(v.updatedAt && { programme_updated_at: v.updatedAt }),
          // Its source did not answer at the latest pull: the programme may be stale.
          ...(v.lastCheck?.status === "failed" && { source_down: true }),
        })),
      });
    },
  );

  return server;
};
