import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Vaakuna's own site: the front page has one `div.MovieCard` per film with its price,
 * runtime, age-limit icon and a table of screenings ("Ti 20.10. klo 14:40", no year).
 * Reservations by phone or email. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/vaakuna.py, AGPL-3.0); re-verified 2026-10-15.
 */
export const VaakunaSite = SiteBase.extend({
  /** The page with the film cards. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type VaakunaSite = z.infer<typeof VaakunaSite>;

export const VAAKUNA_SITES: VaakunaSite[] = defineSites(VaakunaSite, [
  {
    provider: "kinovaakuna",
    name: "Kino Vaakuna",
    homepage: "https://www.kinovaakuna.fi",
    programme: "https://www.kinovaakuna.fi/etusivu.html",
    verifiedAt: "2026-10-15",
    notes:
      "The cinema's page and OSM both give Koulukatu 4 (Leffavuoro's Laurinkatu 48 is out of date), 2026-10-15.",
    venues: [
      {
        slug: "lohja",
        name: "Kino Vaakuna",
        city: "Lohja",
        address: "Koulukatu 4",
        postalCode: "08100",
        geo: { lat: 60.2504641, lon: 24.0675169 },
        geoSource: "osm:way/857803366",
      },
    ],
  },
]);
