import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Suojan elokuvat (Karstula): the front page's poster strip has one `div.poster-info` per
 * film, the title in `h2 a` (`/elokuva/{slug}`) and the screenings as `.showtime-list a`
 * links to `/naytos/{id}` ("pe 16.10. klo 19:00"). Read 2026-10-16; found through
 * nytleffaan.fi's directory.
 */
export const SuojaSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type SuojaSite = z.infer<typeof SuojaSite>;

export const SUOJA_SITES: SuojaSite[] = defineSites(SuojaSite, [
  {
    provider: "suojanelokuvat",
    name: "Suojan elokuvat",
    homepage: "https://suojanelokuvat.fi",
    verifiedAt: "2026-10-16",
    notes:
      "Shows in Suojan talo (Pylkönmäentie 1, 43500 Karstula), address from nytleffaan.fi's directory; OSM has the building. The site sells tickets: each screening's /naytos/ page is copied as its link, never requested.",
    venues: [
      {
        slug: "karstula",
        name: "Suojan elokuvat",
        city: "Karstula",
        address: "Pylkönmäentie 1",
        postalCode: "43500",
        geo: { lat: 62.8739674, lon: 24.8025135 },
        geoSource: "osm:way/1164656839",
      },
    ],
  },
]);
