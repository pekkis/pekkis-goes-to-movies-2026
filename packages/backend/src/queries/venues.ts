import type { z } from "@hono/zod-openapi";
import { sql, type Kysely } from "kysely";
import { jsonObjectFrom } from "kysely/helpers/postgres";
import type { Venue, VenueCheck } from "../api/schemas.ts";
import type { DB } from "../db/types.ts";
import { geoOf, type Bbox } from "./common.ts";

type VenueOut = z.infer<typeof Venue>;

const baseQuery = (db: Kysely<DB>) =>
  db
    .selectFrom("venues as v")
    .innerJoin("providers as p", "p.id", "v.providerId")
    .select([
      "v.id",
      "v.name",
      "v.shortName",
      "v.city",
      "v.address",
      "v.postalCode",
      "v.lat",
      "v.lon",
      "v.url",
      "p.id as providerId",
      "p.name as providerName",
      "p.homepage as providerHomepage",
      "p.booking as providerBooking",
      // The last pull that read the programme, and the latest pull at all.
      sql<string | null>`(
        select to_char(max(c.checked_at) at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
        from venue_checks c
        where c.venue_id = v.id and c.status <> 'failed'
      )`.as("updatedAt"),
    ])
    .select((eb) =>
      jsonObjectFrom(
        eb
          .selectFrom("venueChecks as c")
          .select([
            "c.status",
            sql<string>`to_char(c.checked_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')`.as(
              "checkedAt",
            ),
            "c.message",
          ])
          .whereRef("c.venueId", "=", "v.id")
          .orderBy("c.checkedAt", "desc")
          .limit(1),
      ).as("lastCheck"),
    );

type Row = Awaited<ReturnType<ReturnType<typeof baseQuery>["executeTakeFirstOrThrow"]>>;

const toVenue = (r: Row): VenueOut => ({
  id: r.id,
  name: r.name,
  shortName: r.shortName,
  city: r.city,
  address: r.address,
  postalCode: r.postalCode,
  geo: geoOf(r.lat, r.lon),
  url: r.url,
  provider: {
    id: r.providerId,
    name: r.providerName,
    homepage: r.providerHomepage,
    booking: r.providerBooking,
  },
  updatedAt: r.updatedAt,
  lastCheck: r.lastCheck
    ? {
        status: r.lastCheck.status as z.infer<typeof VenueCheck>["status"],
        checkedAt: r.lastCheck.checkedAt,
        message: r.lastCheck.message,
      }
    : null,
});

/** Venues, optionally inside a map viewport (venues without coordinates are then left out). */
export const listVenues = async (
  db: Kysely<DB>,
  { bbox, city }: { bbox?: Bbox | undefined; city?: string | undefined } = {},
): Promise<VenueOut[]> => {
  let q = baseQuery(db);
  if (bbox) {
    q = q
      .where("v.lat", ">=", bbox.minLat)
      .where("v.lat", "<=", bbox.maxLat)
      .where("v.lon", ">=", bbox.minLon)
      .where("v.lon", "<=", bbox.maxLon);
  }
  if (city) {
    q = q.where((eb) => eb(eb.fn("lower", ["v.city"]), "=", city.toLowerCase()));
  }
  const rows = await q.orderBy("v.city").orderBy("v.name").execute();
  return rows.map(toVenue);
};

export const getVenue = async (db: Kysely<DB>, id: string): Promise<VenueOut | undefined> => {
  const row = await baseQuery(db).where("v.id", "=", id).executeTakeFirst();
  return row && toVenue(row);
};

/** A venue's pull history, newest first: when its programme was read, and when not. */
export const venueChecks = async (
  db: Kysely<DB>,
  venueId: string,
  limit: number,
): Promise<z.infer<typeof VenueCheck>[]> => {
  const rows = await db
    .selectFrom("venueChecks")
    .select([
      sql<string>`to_char(checked_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')`.as(
        "checkedAt",
      ),
      "status",
      "screenings",
      "message",
    ])
    .where("venueId", "=", venueId)
    .orderBy("checkedAt", "desc")
    .limit(limit)
    .execute();
  return rows.map((r) => ({ ...r, status: r.status as z.infer<typeof VenueCheck>["status"] }));
};
