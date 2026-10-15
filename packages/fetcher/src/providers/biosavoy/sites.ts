import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Bio Savoy's Drupal front page: a "Filmvisningar - Sal N" block per hall, each row a link
 * to `/film/{slug}` with the start as a full ISO time in its `content` attribute. Titles
 * are Swedish. Reservations by phone. The host serves plain HTTP only (port 443 refused).
 * Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/biosavoy.py, AGPL-3.0);
 * re-verified 2026-10-15.
 */
export const BioSavoySite = SiteBase.extend({
  /** The site root (http), whose front page carries the programme. */
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
    homepage: "http://www.biosavoy.ax",
    base: "http://www.biosavoy.ax",
    verifiedAt: "2026-10-15",
    notes:
      "HTTP only: biosavoy.ax refuses port 443 (Leffavuoro, re-checked 2026-10-15). Address from the cinema's page (Nygatan 14, AX-22100). City in Finnish like our others.",
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
