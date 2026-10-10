import type { z } from "@hono/zod-openapi";
import type { Kysely } from "kysely";
import type { Venue } from "../api/schemas.ts";
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
    ]);

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
  if (city) q = q.where((eb) => eb(eb.fn("lower", ["v.city"]), "=", city.toLowerCase()));
  const rows = await q.orderBy("v.city").orderBy("v.name").execute();
  return rows.map(toVenue);
};

export const getVenue = async (db: Kysely<DB>, id: string): Promise<VenueOut | undefined> => {
  const row = await baseQuery(db).where("v.id", "=", id).executeTakeFirst();
  return row && toVenue(row);
};
