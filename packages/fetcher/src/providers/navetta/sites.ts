import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Navettakino's front page (its own PHP site since 2026-11, W3.CSS): one card per film, a
 * title, a facts line ("K16, kesto 158 min, liput 11 €") and its screenings under
 * "Näytökset" ("su 01.11 klo 17:00 - Varaa", each linking its reservation page).
 * Weekends only. First mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/navetta.py,
 * AGPL-3.0) for the earlier WordPress page; rewritten 2026-11-01.
 */
export const NavettaSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type NavettaSite = z.infer<typeof NavettaSite>;

export const NAVETTA_SITES: NavettaSite[] = defineSites(NavettaSite, [
  {
    provider: "navettakino",
    name: "Navettakino",
    homepage: "https://www.navettakino.fi",
    verifiedAt: "2026-11-01",
    notes:
      "A cinema in a cowshed in Pyhälahti. Visiting address and GPS (N 62° 48.330′, E 26° 5.232′) from the cinema's contact page, 2026-10-15; not in OSM.",
    venues: [
      {
        slug: "konnevesi",
        name: "Navettakino",
        city: "Konnevesi",
        address: "Pyhälahdentie 972",
        postalCode: "44370",
        geo: { lat: 62.8055, lon: 26.0872 },
        geoSource: "manual",
      },
    ],
  },
]);
