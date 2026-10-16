import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Elokuvateatteri Kaarre (Ivalo, Inari): the municipality's cinema page publishes the
 * week's programme every Tuesday under the heading "…viikon elokuvaesitysten esitysajat…":
 * one paragraph per film with the title in `strong`, rows "Pe 9.10. klo 18" separated by
 * `<br>`, and a facts line "Ikäraja K7, liput 10 €, kesto 1 h 27 min". Read 2026-10-16;
 * found through nytleffaan.fi's directory.
 */
export const KaarreSite = SiteBase.extend({
  /** The municipality's page for the cinema. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KaarreSite = z.infer<typeof KaarreSite>;

export const KAARRE_SITES: KaarreSite[] = defineSites(KaarreSite, [
  {
    provider: "elokuvateatterikaarre",
    name: "Elokuvateatteri Kaarre",
    homepage: "https://www.inari.fi/fi/palvelut/sivistyspalvelut/kulttuuri/elokuvateatteri-kaarre",
    programme: "https://www.inari.fi/fi/palvelut/sivistyspalvelut/kulttuuri/elokuvateatteri-kaarre",
    verifiedAt: "2026-10-16",
    notes:
      "Run by Inari's cultural services in the Kaarre school and cultural centre (Koppelontie 4, 99800 Ivalo, from the page); OSM has the cinema node. Tickets at the door.",
    venues: [
      {
        slug: "ivalo",
        name: "Elokuvateatteri Kaarre",
        city: "Inari",
        address: "Koppelontie 4",
        postalCode: "99800",
        geo: { lat: 68.6626581, lon: 27.5490533 },
        geoSource: "osm:node/13272367602",
      },
    ],
  },
]);
