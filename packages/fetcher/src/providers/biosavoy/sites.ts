import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Bio Savoy's own site (new on 2026-10-28, apparently Statamic): `/spelschema` lists the
 * programme day by day ("Onsdag 28/10", no year), each row linking `/film/{slug}`; each film
 * page has its own schedule with ISO dates (`id="film-day-2026-10-28"`), the hall and the
 * price per show, and the film's age limit and running time. Titles are Swedish. Bookings
 * by phone, tickets at the box office. The old Drupal front page, which Leffavuoro mapped,
 * is gone.
 */
export const BioSavoySite = SiteBase.extend({
  /** The site root, whose `/spelschema` lists the programme. */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type BioSavoySite = z.infer<typeof BioSavoySite>;

export const BIOSAVOY_SITES: BioSavoySite[] = defineSites(BioSavoySite, [
  {
    provider: "biosavoy",
    name: "Bio Savoy",
    homepage: "https://www.biosavoy.ax",
    base: "https://www.biosavoy.ax",
    verifiedAt: "2026-10-28",
    notes:
      "New site 2026-10-28 (HTTPS; the old one served HTTP only). Address from the cinema's page (Nygatan 14, AX-22100). City in Finnish like our others.",
    venues: [
      {
        slug: "maarianhamina",
        name: "Bio Savoy",
        city: "Maarianhamina",
        address: "Nygatan 14",
        postalCode: "22100",
        geo: { lat: 60.1000723, lon: 19.9374255 },
        geoSource: "osm:node/1459454818",
      },
    ],
  },
]);
