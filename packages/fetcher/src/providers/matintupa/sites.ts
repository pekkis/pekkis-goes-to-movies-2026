import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Elokuvateatteri Matin-Tupa's WordPress: `/ohjelmistossa/` renders one block per film
 * with labelled fields (Esitysajat, Liput, Kesto, Genre) and notes. Tickets at the door.
 * Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/matintupa.py, AGPL-3.0);
 * re-verified 2026-10-15.
 */
export const MatinTupaSite = SiteBase.extend({
  /** The programme page. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type MatinTupaSite = z.infer<typeof MatinTupaSite>;

export const MATINTUPA_SITES: MatinTupaSite[] = defineSites(MatinTupaSite, [
  {
    provider: "matintupa",
    name: "Elokuvateatteri Matin-Tupa",
    homepage: "https://www.matin-tupa.fi",
    programme: "https://www.matin-tupa.fi/ohjelmistossa/",
    verifiedAt: "2026-10-15",
    notes:
      "Ylistaro is part of Seinäjoki; the cinema names the village, like Nilsiä and Nummela. OSM gives the street without a number, so no address.",
    venues: [
      {
        slug: "ylistaro",
        name: "Elokuvateatteri Matin-Tupa",
        city: "Ylistaro",
        postalCode: "61400",
        geo: { lat: 62.9456019, lon: 22.5284177 },
        geoSource: "osm:way/243044340",
      },
    ],
  },
]);
