import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Cinemas on the My Calendar WordPress plugin: its public REST route returns the film
 * category's occurrences keyed by date. A page of the cinema's may state one ticket price
 * for every screening. Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/vpk.py,
 * AGPL-3.0); re-verified 2026-10-15.
 */
export const MyCalendarSite = SiteBase.extend({
  /** The WordPress root. */
  base: z.url(),
  /** The film category's numeric id (the name is display text). */
  category: z.number().int(),
  /** The cinema's own page: where screenings link, and where its one price is stated. */
  info: z.url(),
  /** On `info`, the ticket price for every screening ("Elokuvalipun hinta: 12 euroa"). */
  pricePattern: z.string().optional(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type MyCalendarSite = z.infer<typeof MyCalendarSite>;

export const MYCALENDAR_SITES: MyCalendarSite[] = defineSites(MyCalendarSite, [
  {
    provider: "pyhasalmenvpk",
    name: "Pyhäsalmen VPK",
    homepage: "https://www.pyhasalmenvpk.fi/pyhasalmen-vpkn-elokuvat",
    base: "https://www.pyhasalmenvpk.fi",
    category: 1,
    info: "https://www.pyhasalmenvpk.fi/pyhasalmen-vpkn-elokuvat",
    pricePattern: "Elokuvalipun\\s+hinta\\s*:?\\s*(\\d{1,3}(?:[.,]\\d{1,2})?)\\s*euroa",
    verifiedAt: "2026-10-15",
    notes:
      "A volunteer fire brigade's cinema since 1944. Address from its page (Palotie 4, 86800 Pyhäsalmi); OSM has the building unnamed, so the point is geocoded. Pyhäsalmi is the centre of Pyhäjärvi.",
    venues: [
      {
        slug: "pyhajarvi",
        name: "Pyhäsalmen VPK",
        city: "Pyhäjärvi",
        address: "Palotie 4",
        postalCode: "86800",
        geo: { lat: 63.6828497, lon: 25.9734188 },
        geoSource: "nominatim",
      },
    ],
  },
]);
