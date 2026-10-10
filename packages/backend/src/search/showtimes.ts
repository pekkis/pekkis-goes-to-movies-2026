import { sql, type Kysely, type Selectable } from "kysely";
import type { DB } from "../db/types.ts";
import type { ScreeningFilter } from "./filters.ts";

/**
 * Fuzzy film search plus the screenings of the films found.
 *
 * A "hit" is either a TMDB film (matched on its fi/sv/en/original titles and on the titles
 * cinemas list it under) or a cinema listing with no TMDB film (an opera, an unmatched film),
 * matched on its own titles. Scores are pg_trgm `word_similarity` (0..1), so typos and
 * partial names work: "odysey" finds The Odyssey.
 */

export const DEFAULT_MIN_SCORE = 0.5;

export type Hit =
  | { kind: "film"; id: string; score: number }
  | { kind: "listing"; id: string; score: number };

/** `greatest(word_similarity(term, col1), …)`, treating NULL titles as no match. */
const similarity = (term: string, columns: string[]) =>
  sql<number>`greatest(${sql.join(
    columns.map((c) => sql`word_similarity(${term}, coalesce(${sql.ref(c)}, ''))`),
  )})`;

export const searchFilms = async (
  db: Kysely<DB>,
  term: string,
  { minScore = DEFAULT_MIN_SCORE, limit = 10 } = {},
): Promise<Hit[]> => {
  const { rows } = await sql<{ kind: "film" | "listing"; id: string; score: number }>`
    with hits as (
      select 'film' as kind, f.id,
        greatest(
          ${similarity(term, ["f.title_fi", "f.title_sv", "f.title_en", "f.original_title"])},
          coalesce((
            select max(${similarity(term, ["l.title_fi", "l.title_sv", "l.title_en"])})
            from film_listings l where l.film_id = f.id
          ), 0)
        ) as score
      from films f
      union all
      select 'listing' as kind, l.id,
        ${similarity(term, ["l.title_fi", "l.title_sv", "l.title_en", "l.original_title"])} as score
      from film_listings l
      where l.film_id is null
    )
    select kind, id, score::float8 as score from hits
    where score >= ${minScore}
    order by score desc, id
    limit ${limit}
  `.execute(db);
  return rows;
};

export type ShowtimeRow = {
  startsAt: Date;
  /** The film's title: TMDB's Finnish one, else the cinema's. */
  film: string;
  city: string;
  venue: string;
  screen: string | null;
  audio: string[];
  subtitlesKind: string;
  subtitlesLanguages: string[];
  formats: string[];
  licensed: boolean | null;
  ageLimit: string | null;
  availability: string;
  ticketUrl: string | null;
  /** Great-circle distance from the --near point; null without one. */
  distanceKm: number | null;
};

/** Haversine distance in km from a point to the venue (`v`), in SQL. */
const distanceKm = (lat: number, lon: number) => sql<number>`(
  2 * 6371 * asin(sqrt(
    power(sin(radians(v.lat - ${lat}) / 2), 2)
    + cos(radians(${lat})) * cos(radians(v.lat)) * power(sin(radians(v.lon - ${lon}) / 2), 2)
  ))
)`;

/**
 * Screenings on one business date, in start order: of one film (or unmatched listing), or
 * of every film when `hit` is undefined. Optionally only from some providers, within a
 * radius (venues without coordinates are then left out) and from a time of day on.
 */
export const screeningsFor = async (
  db: Kysely<DB>,
  hit: Hit | undefined,
  businessDate: string,
  { providerIds, near, after }: ScreeningFilter = {},
): Promise<ShowtimeRow[]> => {
  let q = db
    .selectFrom("screenings as s")
    .innerJoin("venues as v", "v.id", "s.venueId")
    .innerJoin("filmListings as l", "l.id", "s.listingId")
    .leftJoin("films as f", "f.id", "s.filmId")
    .leftJoin("auditoriums as a", "a.id", "s.auditoriumId")
    .select([
      "s.startsAt",
      sql<string>`coalesce(f.title_fi, l.title_fi, f.title_en, f.original_title, l.title_en, l.original_title, l.id)`.as(
        "film",
      ),
      "v.city",
      "v.name as venue",
      "a.name as screen",
      "s.audio",
      "s.subtitlesKind",
      "s.subtitlesLanguages",
      "s.formats",
      "s.licensed",
      "s.ageLimit",
      "s.availability",
      "s.ticketUrl",
      (near ? distanceKm(near.lat, near.lon) : sql<number | null>`null::float8`).as("distanceKm"),
    ])
    .where("s.businessDate", "=", businessDate)
    .where("s.removedAt", "is", null);
  if (hit) q = q.where(hit.kind === "film" ? "s.filmId" : "s.listingId", "=", hit.id);
  if (after) {
    q = q.where(
      "s.startsAt",
      ">=",
      sql<Date>`(${businessDate}::date + ${after}::time) at time zone 'Europe/Helsinki'`,
    );
  }
  if (providerIds) q = q.where("s.providerId", "in", providerIds.length ? providerIds : [""]);
  if (near) q = q.where(distanceKm(near.lat, near.lon), "<=", near.radiusKm);
  return q.orderBy("s.startsAt").orderBy("v.city").orderBy("film").execute();
};

export type ListingDetails = Selectable<DB["filmListings"]>;

export type FilmDetails = Selectable<DB["films"]> & {
  /** The Finnish title cinemas use, for films TMDB has no Finnish title for. */
  localTitle: string | null;
};

export const filmDetails = (db: Kysely<DB>, id: string): Promise<FilmDetails | undefined> =>
  db
    .selectFrom("films as f")
    .selectAll("f")
    .select((eb) =>
      eb
        .selectFrom("filmListings as l")
        .select("l.titleFi")
        .whereRef("l.filmId", "=", "f.id")
        .where("l.titleFi", "is not", null)
        .orderBy("l.id")
        .limit(1)
        .as("localTitle"),
    )
    .where("f.id", "=", id)
    .executeTakeFirst();

export const listingDetails = (db: Kysely<DB>, id: string): Promise<ListingDetails | undefined> =>
  db.selectFrom("filmListings").selectAll().where("id", "=", id).executeTakeFirst();

/** Today's business date in Helsinki, from the database clock. */
export const helsinkiToday = async (db: Kysely<DB>): Promise<string> => {
  const { rows } = await sql<{ today: string }>`
    select ((now() at time zone 'Europe/Helsinki')::date)::text as today
  `.execute(db);
  return rows[0]!.today;
};
