import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Tervakoski (Janakkala): the municipality's programme page lists days in bold
 * ("Keskiviikko 14.10.") and below each a paragraph per screening ("Klo 17.00 – Pirjo i
 * Sverige (S), kotimainen, komedia, kesto 1 t 28 min, lippu 10,00 €"), up to a separator.
 * Read 2026-10-15; the site was found by the maintainer.
 */
export const TervakoskiSite = SiteBase.extend({
  /** The programme page. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type TervakoskiSite = z.infer<typeof TervakoskiSite>;

export const TERVAKOSKI_SITES: TervakoskiSite[] = defineSites(TervakoskiSite, [
  {
    provider: "kinotervakoski",
    name: "Kino Tervakoski",
    homepage: "https://www.janakkala.fi/kino/",
    programme: "https://www.janakkala.fi/kino/ohjelmisto-2-2-2/",
    verifiedAt: "2026-10-15",
    notes:
      "Run by Janakkala's youth services in Tervakosken Seuratalo (Seuranaukio 3, 12400 Tervakoski), from the cinema's contact page; OSM has the cinema node. The programme page's path is the municipality's, and may change.",
    venues: [
      {
        slug: "tervakoski",
        name: "Kino Tervakoski",
        city: "Janakkala",
        address: "Seuranaukio 3",
        postalCode: "12400",
        geo: { lat: 60.8113829, lon: 24.6244573 },
        geoSource: "osm:node/2923518604",
      },
    ],
  },
]);
