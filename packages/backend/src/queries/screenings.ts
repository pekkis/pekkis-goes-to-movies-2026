import type { z } from "@hono/zod-openapi";
import { sql, type Kysely } from "kysely";
import type { Screening } from "../api/schemas.ts";
import type { DB } from "../db/types.ts";
import { toHelsinkiIso } from "../lib/time.ts";
import { geoOf, toFilmSummary, type Bbox } from "./common.ts";

type ScreeningOut = z.infer<typeof Screening>;

export type ScreeningFilter = {
  /** Business date, YYYY-MM-DD. */
  date: string;
  bbox?: Bbox | undefined;
  venueId?: string | undefined;
  /** A TMDB film id (`tmdb:…`) or a listing id. */
  filmId?: string | undefined;
  /** "HH:MM", Helsinki time on `date`; later shows (also after midnight) are kept. */
  after?: string | undefined;
  limit: number;
  cursor?: Cursor | undefined;
};

/** Keyset position: the last row of the previous page. */
export type Cursor = { startsAt: string; id: string };

export const encodeCursor = (c: Cursor): string =>
  Buffer.from(`${c.startsAt}|${c.id}`).toString("base64url");

export const decodeCursor = (raw: string): Cursor | undefined => {
  const [startsAt, id] = Buffer.from(raw, "base64url").toString("utf8").split("|");
  if (!startsAt || !id || Number.isNaN(Date.parse(startsAt))) return undefined;
  return { startsAt, id };
};

/** Screenings not removed upstream, in start order, one page at a time. */
export const listScreenings = async (
  db: Kysely<DB>,
  f: ScreeningFilter,
): Promise<{ items: ScreeningOut[]; nextCursor: Cursor | null }> => {
  let q = db
    .selectFrom("screenings as s")
    .innerJoin("venues as v", "v.id", "s.venueId")
    .innerJoin("filmListings as l", "l.id", "s.listingId")
    .leftJoin("films as f", "f.id", "s.filmId")
    .leftJoin("auditoriums as a", "a.id", "s.auditoriumId")
    .select([
      "s.id",
      "s.startsAt",
      "s.endsAt",
      "s.businessDate",
      "s.projection",
      "s.dimension",
      "s.formats",
      "s.audio",
      "s.dubbed",
      "s.subtitlesKind",
      "s.subtitlesLanguages",
      "s.tags",
      "s.series",
      "s.ageLimit",
      "s.availability",
      "s.priceAmountCents",
      "s.priceCurrency",
      "s.priceNote",
      "s.ticketUrl",
      "s.filmId",
      "s.listingId",
      "v.id as venueId",
      "v.name as venueName",
      "v.city as venueCity",
      "v.lat as venueLat",
      "v.lon as venueLon",
      "a.name as auditorium",
      "l.kind as listingKind",
      "l.titleFi as listingTitleFi",
      "l.titleEn as listingTitleEn",
      "l.originalTitle as listingOriginalTitle",
      "l.year as listingYear",
      "l.runtimeMinutes as listingRuntime",
      "l.rating as listingRating",
      "f.titleFi as filmTitleFi",
      "f.titleEn as filmTitleEn",
      "f.originalTitle as filmOriginalTitle",
      "f.releaseDate as filmReleaseDate",
      "f.runtimeMinutes as filmRuntime",
      "f.rating as filmRating",
      "f.posterPath as filmPosterPath",
    ])
    .where("s.businessDate", "=", f.date)
    .where("s.removedAt", "is", null);

  if (f.bbox) {
    q = q
      .where("v.lat", ">=", f.bbox.minLat)
      .where("v.lat", "<=", f.bbox.maxLat)
      .where("v.lon", ">=", f.bbox.minLon)
      .where("v.lon", "<=", f.bbox.maxLon);
  }
  if (f.venueId) q = q.where("s.venueId", "=", f.venueId);
  if (f.filmId) {
    const id = f.filmId;
    q = q.where((eb) => eb.or([eb("s.filmId", "=", id), eb("s.listingId", "=", id)]));
  }
  if (f.after) {
    q = q.where(
      "s.startsAt",
      ">=",
      sql<Date>`(${f.date}::date + ${f.after}::time) at time zone 'Europe/Helsinki'`,
    );
  }
  if (f.cursor) {
    q = q.where(
      sql<boolean>`(s.starts_at, s.id) > (${f.cursor.startsAt}::timestamptz, ${f.cursor.id})`,
    );
  }

  const rows = await q
    .orderBy("s.startsAt")
    .orderBy("s.id")
    .limit(f.limit + 1)
    .execute();
  const page = rows.slice(0, f.limit);
  const last = page.at(-1);
  return {
    items: page.map((r) => ({
      id: r.id,
      startsAt: toHelsinkiIso(r.startsAt),
      endsAt: r.endsAt && toHelsinkiIso(r.endsAt),
      businessDate: r.businessDate,
      venue: {
        id: r.venueId,
        name: r.venueName,
        city: r.venueCity,
        geo: geoOf(r.venueLat, r.venueLon),
      },
      auditorium: r.auditorium,
      film: toFilmSummary(r),
      projection: r.projection,
      dimension: r.dimension,
      formats: r.formats,
      audio: r.audio,
      dubbed: r.dubbed,
      subtitles: { kind: r.subtitlesKind, languages: r.subtitlesLanguages },
      tags: r.tags,
      series: r.series,
      ageLimit: r.ageLimit,
      availability: r.availability,
      price:
        r.priceAmountCents !== null && r.priceCurrency !== null
          ? { amountCents: r.priceAmountCents, currency: r.priceCurrency, note: r.priceNote }
          : null,
      ticketUrl: r.ticketUrl,
    })),
    nextCursor:
      rows.length > f.limit && last ? { startsAt: last.startsAt.toISOString(), id: last.id } : null,
  };
};
