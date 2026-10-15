import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Bio Pallas's Wix front page, server-rendered. The rich-text blocks in order are the
 * structure: a title block ("Kerro kaikille", an optional version, "1h 52min -K12-"), a
 * date-and-time block ("Ke/Ons 14.10", "Klo 19.00") and a price block ("13€"). Bilingual
 * (Finnish/Swedish), no year. Tickets at the door. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/pallas.py, AGPL-3.0); re-verified 2026-10-15.
 */
export const BioPallasSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type BioPallasSite = z.infer<typeof BioPallasSite>;

export const BIOPALLAS_SITES: BioPallasSite[] = defineSites(BioPallasSite, [
  {
    provider: "biopallas",
    name: "Bio Pallas",
    homepage: "https://www.biopallas.com",
    verifiedAt: "2026-10-15",
    notes:
      "The funkis cinema in Karjaa (Raasepori), since 1923. Neither the page nor OSM gives a house number, so no address.",
    venues: [
      {
        slug: "karjaa",
        name: "Bio Pallas",
        city: "Raasepori",
        geo: { lat: 60.0695118, lon: 23.6582666 },
        geoSource: "osm:node/2068950851",
      },
    ],
  },
]);
