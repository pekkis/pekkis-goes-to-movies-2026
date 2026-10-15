import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Lieksan Kino's hand-written page: `#section-b` ("Elokuvissa nyt") has one
 * `article.entry` per film with its price, runtime, rating icon and screenings
 * ("La 17.10. 15.00"); `#section-c` is coming soon and is not read. Tickets at the door.
 * Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/lieksa.py, AGPL-3.0);
 * re-verified 2026-10-15.
 */
export const LieksaSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type LieksaSite = z.infer<typeof LieksaSite>;

export const LIEKSA_SITES: LieksaSite[] = defineSites(LieksaSite, [
  {
    provider: "lieksankino",
    name: "Lieksan Kino",
    homepage: "https://www.lieksanelokuvat.net",
    verifiedAt: "2026-10-15",
    notes:
      "In the culture centre's Brahe hall (Pielisentie 9–11, from the cinema's page), 2026-10-15.",
    venues: [
      {
        slug: "lieksa",
        name: "Lieksan Kino",
        city: "Lieksa",
        address: "Pielisentie 9–11",
        postalCode: "81720",
        geo: { lat: 63.316802, lon: 30.0325327 },
        geoSource: "osm:node/14184528958",
      },
    ],
  },
]);
