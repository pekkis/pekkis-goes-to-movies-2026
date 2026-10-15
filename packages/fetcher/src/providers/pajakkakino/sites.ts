import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Pajakkakino (Kuhmo): one WordPress post per film, read through the public REST route.
 * A film post has a facts line ("Draama I 1h 57min I 2.10.2026 I AUDIO englanti TEKSTIT
 * suomi"), the age image, and an "ESITYKSET:" list ("PE 16.10. KLO 15:30"); a cancelled
 * screening is struck through (`<del>`). Read 2026-10-15; found through elokuviin.com's list
 * of cinemas.
 */
export const PajakkakinoSite = SiteBase.extend({
  /** The WordPress root; posts are `{base}/wp-json/wp/v2/posts`. */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type PajakkakinoSite = z.infer<typeof PajakkakinoSite>;

export const PAJAKKAKINO_SITES: PajakkakinoSite[] = defineSites(PajakkakinoSite, [
  {
    provider: "pajakkakino",
    name: "Pajakkakino",
    homepage: "https://www.pajakkakino.fi",
    base: "https://www.pajakkakino.fi",
    titlePrefixes: {
      Romppaviikot: { series: "Romppaviikot" },
      Romppaviikko: { series: "Romppaviikot" },
    },
    verifiedAt: "2026-10-15",
    notes:
      "Address and coordinates from OSM (Rajakatu 56, 88900 Kuhmo), 2026-10-15. Tickets at the box office or reserved by phone; the reservation page is never requested. Prices depend on age and length, so none is published.",
    venues: [
      {
        slug: "kuhmo",
        name: "Pajakkakino",
        city: "Kuhmo",
        address: "Rajakatu 56",
        postalCode: "88900",
        geo: { lat: 64.1257339, lon: 29.5195518 },
        geoSource: "osm:way/238296413",
      },
    ],
  },
]);
