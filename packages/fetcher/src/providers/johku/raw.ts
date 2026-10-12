import { z } from "zod";

/**
 * Johku storefront schedule: `https://{host}/api/{shop}/fi_FI/showschedule.json?…`, the
 * endpoint the storefront's own code builds (`useAsyncData`), called anonymously: the
 * storefront adds `X-ApiKey` only for signed-in users. Values are mostly strings.
 * Profiled 2026-10-12 over 7 storefronts.
 */

const flag = z.union([z.string(), z.number()]).nullish();

export const JohkuEntry = z.looseObject({
  id: z.union([z.string(), z.number()]).transform(String),
  /** The title as the cinema writes it ("Perhekino: Unohdettu Saari"). */
  text: z.string(),
  /** Helsinki local time, "2026-10-14 19:00". Coming-soon entries: "… 00:00". */
  start_date: z.string(),
  resource_name: z.string().nullish(),
  resource_capacity: flag,
  /** Seats taken. */
  resource_reservations: flag,
  /** "1": coming soon, no showtime yet. */
  upcoming: flag,
  hideinternet: flag,
  /** "13", "12.5"; null for entries that are not public screenings. */
  price: flag,
  /** "1": several ticket types; `price` is the base one ("Elokuva 13 €"). */
  multipleprices: flag,
  originaltitle: z.string().nullish(),
  duration: flag,
  imdb: z.string().nullish(),
  /** Maccs Box (distributors' database) codes: "FI", "OV", "FI-SE", "XX", "-". */
  maccsboxlanguage: z.string().nullish(),
  maccsboxsubtitles: z.string().nullish(),
  director: z.string().nullish(),
  /** "K-12", "S", "-". */
  agelimit: z.string().nullish(),
  /** The film's storefront page; copied as the ticket link. */
  storefronturl: z.string().nullish(),
  product: z.looseObject({
    id: z.union([z.string(), z.number()]).transform(String),
    enable_catalog: flag,
    enable_collection: flag,
  }),
});
export type JohkuEntry = z.infer<typeof JohkuEntry>;

export const ScheduleResponse = z.looseObject({ data: z.array(z.unknown()) });

export type JohkuRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** category id -> response */
  schedules: Record<string, unknown>;
};
