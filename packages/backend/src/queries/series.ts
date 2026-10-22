import { sql, type Kysely } from "kysely";
import type { DB } from "../db/types.ts";

export type SeriesOut = {
  id: string;
  name: string;
  /** "strand", "festival", "club", "theme-week", "distributor-series", … */
  kind: string;
  /** Screenings (not removed) between the days asked for. */
  screenings: number;
  firstDay: string;
};

/** `%` and `_` in a user's text are literal in ILIKE. */
export const likeText = (text: string): string => `%${text.replace(/[\\%_]/g, (c) => `\\${c}`)}%`;

/**
 * Series with screenings (not removed) between `from` and `to`: the cinemas' own strands
 * (Kino Regina's director series, Kahvikino), festivals, clubs and distributors' series.
 * `query` keeps those whose name or id contains it ("suleiman", "neule"). Most screenings
 * first.
 */
export const listSeries = async (
  db: Kysely<DB>,
  from: string,
  to: string,
  query?: string,
): Promise<SeriesOut[]> => {
  let q = db
    .selectFrom("series as se")
    .innerJoin("screenings as s", (join) =>
      join.on(sql<boolean>`se.id = any(s.series)`).on("s.removedAt", "is", null),
    )
    .select([
      "se.id",
      "se.name",
      "se.kind",
      sql<number>`count(s.id)::int`.as("screenings"),
      sql<string>`min(s.business_date)::text`.as("firstDay"),
    ])
    .where(sql<boolean>`s.business_date between ${from}::date and ${to}::date`)
    .groupBy(["se.id", "se.name", "se.kind"]);
  if (query) {
    const like = likeText(query);
    q = q.where((eb) => eb.or([eb("se.name", "ilike", like), eb("se.id", "ilike", like)]));
  }
  return q.orderBy("screenings", "desc").orderBy("se.name").execute();
};
