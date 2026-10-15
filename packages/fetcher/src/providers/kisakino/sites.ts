import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * KisaKino (Saarijärvi), run by the sports club Pullistus: the front page links each film
 * (`h2.etusivu-otsikko a`) and shows only its next three screenings; the film's own page
 * lists them all in the sidebar ("La 24.10.2026 16:00"), with the runtime, the price and
 * the age image. Read 2026-10-15; found through elokuviin.com's list of cinemas.
 */
export const KisaKinoSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KisaKinoSite = z.infer<typeof KisaKinoSite>;

export const KISAKINO_SITES: KisaKinoSite[] = defineSites(KisaKinoSite, [
  {
    provider: "kisakino",
    name: "KisaKino",
    homepage: "https://kisakino.fi",
    verifiedAt: "2026-10-15",
    notes:
      'Shows in the Saarijärvi hall of the town hall (Sivulantie 11), the OSM node of the town hall. Tickets at the box office before the show ("lippukassalta ennen elokuvaa").',
    venues: [
      {
        slug: "saarijarvi",
        name: "KisaKino",
        city: "Saarijärvi",
        address: "Sivulantie 11",
        postalCode: "43100",
        geo: { lat: 62.7071042, lon: 25.2536407 },
        geoSource: "osm:node/85194079",
      },
    ],
  },
]);
