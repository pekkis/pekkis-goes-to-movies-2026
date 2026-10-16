import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Rio (Suonenjoki): the WordPress front page has one block per film between `<hr>`s,
 * the title in `p strong`, then a list of rows "Pe 16.10. klo 18.30" with the film's facts
 * on the same lines ("Kesto: 2 h 8 min", "Ikäraja: K-12", "Liput: 15 €") and notes below
 * ("puhuttu suomeksi"). Read 2026-10-16; found through nytleffaan.fi's directory.
 */
export const KinoRioSite = SiteBase.extend({
  /** The page with the programme. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KinoRioSite = z.infer<typeof KinoRioSite>;

export const KINORIO_SITES: KinoRioSite[] = defineSites(KinoRioSite, [
  {
    provider: "kinorio",
    name: "Kino Rio",
    homepage: "https://kinorio.fi",
    programme: "https://kinorio.fi/",
    verifiedAt: "2026-10-16",
    notes:
      "Address from nytleffaan.fi's directory (Asemakatu 1, 77600 Suonenjoki); OSM has the cinema node. The next week (Fri–Thu) is published by Tuesday. Tickets at the door.",
    venues: [
      {
        slug: "suonenjoki",
        name: "Kino Rio",
        city: "Suonenjoki",
        address: "Asemakatu 1",
        postalCode: "77600",
        geo: { lat: 62.6262457, lon: 27.1267933 },
        geoSource: "osm:node/603326022",
      },
    ],
  },
]);
