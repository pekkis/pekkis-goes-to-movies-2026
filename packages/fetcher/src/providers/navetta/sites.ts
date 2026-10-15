import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Navettakino's front page (WordPress blocks, prose): after "Tulevan viikonlopun
 * näytökset", screening lines ("Pirjo i Sverige la 17.10 klo 15:00", or a title line then
 * the date) and film blocks whose facts line reads "Kesto 1 h 27 min, K12, liput 10 €".
 * Weekends only, tickets at the door. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/navetta.py, AGPL-3.0); re-verified 2026-10-15.
 */
export const NavettaSite = SiteBase.extend({
  /** The paragraph that opens the screenings. */
  heading: z.string().min(1),
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
    heading: "Tulevan viikonlopun näytökset",
    verifiedAt: "2026-10-15",
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
