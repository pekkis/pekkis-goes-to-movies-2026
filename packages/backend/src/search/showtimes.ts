import { sql, type Kysely, type Selectable } from "kysely";
import type { DB } from "../db/types.ts";

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
};

/** Screenings of a film (or of an unmatched listing) on one business date, in start order. */
export const screeningsFor = (
  db: Kysely<DB>,
  hit: Hit,
  businessDate: string,
): Promise<ShowtimeRow[]> =>
  db
    .selectFrom("screenings as s")
    .innerJoin("venues as v", "v.id", "s.venueId")
    .leftJoin("auditoriums as a", "a.id", "s.auditoriumId")
    .select([
      "s.startsAt",
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
    ])
    .where(hit.kind === "film" ? "s.filmId" : "s.listingId", "=", hit.id)
    .where("s.businessDate", "=", businessDate)
    .where("s.removedAt", "is", null)
    .orderBy("s.startsAt")
    .orderBy("v.city")
    .execute();

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
