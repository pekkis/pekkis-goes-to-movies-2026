import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino-Kuva (Teuva): the front page (ISO-8859-1) has one table row per film, the title in
 * `td.elokuva h1` with "Kesto: 1 h 52 min -K12-", and a `pre` of rows ("KE 14.10. KLO
 * 19.00", "TO 15.10. KLO 14.00 JA KLO 17.00"), notes and the price ("Liput 14,-"). Read
 * 2026-10-15; the site was found by the maintainer.
 */
export const KinoKuvaSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KinoKuvaSite = z.infer<typeof KinoKuvaSite>;

export const KINOKUVA_SITES: KinoKuvaSite[] = defineSites(KinoKuvaSite, [
  {
    provider: "kinokuva",
    name: "Kino-Kuva",
    homepage: "https://www.kinokuva.fi",
    verifiedAt: "2026-10-15",
    notes:
      "Address from the cinema's contact page (Porvarintie 28, 64700 Teuva); OSM has the cinema node. Tickets at the door.",
    venues: [
      {
        slug: "teuva",
        name: "Kino-Kuva",
        city: "Teuva",
        address: "Porvarintie 28",
        postalCode: "64700",
        geo: { lat: 62.4837315, lon: 21.7456309 },
        geoSource: "osm:node/12114490417",
      },
    ],
  },
]);
