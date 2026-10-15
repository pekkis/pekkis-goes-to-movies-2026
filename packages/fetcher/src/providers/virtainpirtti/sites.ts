import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Virtain Pirtti (Virrat): the "Ohjelmistossa nyt" page (Weebly) has one `div.paragraph`
 * per film, its lines split by `<br>`: "Kerro kaikille K-12", notes ("Ennakkonäytös"), rows
 * ("pe 16.10. klo 15.15*"), a footnote for the starred rows ("*16.10. ja 21.10. tekstitys
 * suomeksi") and "Kesto 1 h 52 min". Read 2026-10-15; the site was found by the maintainer.
 */
export const VirtainPirttiSite = SiteBase.extend({
  /** The programme page. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type VirtainPirttiSite = z.infer<typeof VirtainPirttiSite>;

export const VIRTAINPIRTTI_SITES: VirtainPirttiSite[] = defineSites(VirtainPirttiSite, [
  {
    provider: "virtainpirtti",
    name: "Virtain Pirtti",
    homepage: "https://www.virtainpirtti.fi",
    programme: "https://www.virtainpirtti.fi/ohjelmistossa-nyt.html",
    verifiedAt: "2026-10-15",
    notes:
      "The site states no street address; address and coordinates from OSM (Virtaintie 15, 34800 Virrat), 2026-10-15. Tickets at the door.",
    venues: [
      {
        slug: "virrat",
        name: "Virtain Pirtti",
        city: "Virrat",
        address: "Virtaintie 15",
        postalCode: "34800",
        geo: { lat: 62.2349819, lon: 23.778714 },
        geoSource: "osm:node/13028491186",
      },
    ],
  },
]);
