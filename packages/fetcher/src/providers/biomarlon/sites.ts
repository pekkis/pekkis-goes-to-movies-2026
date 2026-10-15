import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Bio Marlon (Kauhajoki): an Elementor front page with one text block per film, the title
 * in `h1`, one `h4` per screening ("pe 16.10. 19:00", "Ensi-ilta pe 16.10. 15:30") and a
 * facts paragraph ("K-12 1 t 45 min 14 €"). Read 2026-10-15; the site was found by the
 * maintainer.
 */
export const BioMarlonSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type BioMarlonSite = z.infer<typeof BioMarlonSite>;

export const BIOMARLON_SITES: BioMarlonSite[] = defineSites(BioMarlonSite, [
  {
    provider: "biomarlon",
    name: "Bio Marlon",
    homepage: "https://biomarlon.fi",
    verifiedAt: "2026-10-15",
    notes:
      "Address from the cinema's page (Topeeka 37, 61800 Kauhajoki); OSM has the cinema node. Tickets at the door. The programme is published on Mondays, 1.5 weeks ahead.",
    venues: [
      {
        slug: "kauhajoki",
        name: "Bio Marlon",
        city: "Kauhajoki",
        address: "Topeeka 37",
        postalCode: "61800",
        geo: { lat: 62.4268891, lon: 22.179885 },
        geoSource: "osm:node/11608807439",
      },
    ],
  },
]);
