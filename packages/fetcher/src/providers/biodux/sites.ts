import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Bio Dux (Kristiinankaupunki): a bilingual BaseKit front page read as lines. A film is a
 * title ("Forgotten Island 109 min"; "Matka Piemonteen - Resan till Piemonte" is Finnish
 * and Swedish), its rows ("fre/pe 16.10. 18.00", "lör 17.10. 12.30 på svenska"), language
 * and genre lines, and "åldersgräns 7 ikäraja", which closes it. Read 2026-10-16; found
 * through nytleffaan.fi's directory.
 */
export const BioDuxSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type BioDuxSite = z.infer<typeof BioDuxSite>;

export const BIODUX_SITES: BioDuxSite[] = defineSites(BioDuxSite, [
  {
    provider: "biodux",
    name: "Bio Dux",
    homepage: "https://biodux.fi",
    verifiedAt: "2026-10-16",
    notes:
      "Strandgatan 22 / Rantakatu 22, 64100 Kristiinankaupunki (nytleffaan.fi's directory); OSM has the cinema node. Tickets at the door; almost every film has Swedish subtitles.",
    venues: [
      {
        slug: "kristiinankaupunki",
        name: "Bio Dux",
        city: "Kristiinankaupunki",
        address: "Rantakatu 22",
        postalCode: "64100",
        geo: { lat: 62.2774278, lon: 21.380057 },
        geoSource: "osm:node/497658159",
      },
    ],
  },
]);
