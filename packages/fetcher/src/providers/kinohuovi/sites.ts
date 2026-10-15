import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino-Huovi's Duda front page: one `.postArticle` card per film whose text carries its
 * screenings ("23.-27.10. PE, LA, SU, MA ja TI klo 18.00"), runtime and price. No year,
 * no rating. Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/kinohuovi.py,
 * AGPL-3.0); re-verified 2026-10-15.
 */
export const KinoHuoviSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KinoHuoviSite = z.infer<typeof KinoHuoviSite>;

export const KINOHUOVI_SITES: KinoHuoviSite[] = defineSites(KinoHuoviSite, [
  {
    provider: "kinohuovi",
    name: "Kino-Huovi",
    homepage: "https://www.kinohuovi.fi",
    verifiedAt: "2026-10-15",
    notes:
      "Address from the cinema's page and OSM (Harjavallankatu 33, 29200 Harjavalta), 2026-10-15.",
    venues: [
      {
        slug: "harjavalta",
        name: "Kino-Huovi",
        city: "Harjavalta",
        address: "Harjavallankatu 33",
        postalCode: "29200",
        geo: { lat: 61.3168674, lon: 22.139273 },
        geoSource: "osm:way/1154064070",
      },
    ],
  },
]);
