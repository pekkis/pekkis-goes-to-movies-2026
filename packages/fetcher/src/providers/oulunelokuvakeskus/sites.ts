import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Oulun Elokuvakeskus (Oulu Film Centre) and its cinema Studio, in Kulttuuritalo Valve:
 * the programme page lists a month, one table per show. A film's first show is a
 * `table.premiere` with everything (director, title in bold, original title, countries and
 * year, runtime, notes and price, the age limit as an image's title, the IMDb link); later
 * shows are `table.regular` with the title only. A row without a date has the date above
 * it. Read 2026-10-30; found through elokuviin.com.
 */
export const OulunElokuvakeskusSite = SiteBase.extend({
  /** The page with the programme. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type OulunElokuvakeskusSite = z.infer<typeof OulunElokuvakeskusSite>;

export const OULUNELOKUVAKESKUS_SITES: OulunElokuvakeskusSite[] = defineSites(
  OulunElokuvakeskusSite,
  [
    {
      provider: "oulunelokuvakeskus",
      name: "Oulun Elokuvakeskus",
      homepage: "https://www.oulunelokuvakeskus.fi",
      programme: "https://www.oulunelokuvakeskus.fi/oek/studio/ohjelma",
      verifiedAt: "2026-10-30",
      // A daytime show with cheaper tickets for pensioners, students and the unemployed.
      titlePrefixes: { Matineanäytös: {} },
      notes:
        "Tickets at Valve's box office and on Ticketmaster; the screenings link Ticketmaster's venue page, copied from the programme. A festival block (Oulu's children's film festival) only links the festival's site and has no shows here.",
      venues: [
        {
          slug: "studio",
          name: "Studio",
          city: "Oulu",
          address: "Hallituskatu 7",
          postalCode: "90100",
          // Kulttuuritalo Valve; OSM does not list Studio as a cinema.
          geo: { lat: 65.014191, lon: 25.47028 },
          geoSource: "nominatim",
        },
      ],
    },
  ],
);
