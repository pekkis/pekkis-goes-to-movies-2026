import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kurikan Kino's front page: one `li.elokuva-thumb` card per film, its showtimes as
 * `span.elokuva-aika` with a stamp in `esitysaika` (the local time written as UTC) and
 * "pe 9.10. 19:00" beside it, plus the runtime, the price and the age class. Read 2026-10-15; found through
 * elokuviin.com's list of cinemas.
 */
export const KurikanKinoSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KurikanKinoSite = z.infer<typeof KurikanKinoSite>;

export const KURIKANKINO_SITES: KurikanKinoSite[] = defineSites(KurikanKinoSite, [
  {
    provider: "kurikankino",
    name: "Kurikan Kino",
    homepage: "https://www.kurikankino.com",
    verifiedAt: "2026-10-15",
    notes:
      "Address from the cinema's contact page (Kankaantie 4, 61300 Kurikka); OSM has the building. The site states no way of buying tickets, so screenings link to the film's page.",
    venues: [
      {
        slug: "kurikka",
        name: "Kurikan Kino",
        city: "Kurikka",
        address: "Kankaantie 4",
        postalCode: "61300",
        geo: { lat: 62.6138294, lon: 22.3992623 },
        geoSource: "osm:way/579209288",
      },
    ],
  },
]);
