import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Vimpelin Nuorisokuvat (Vimpeli), the cinema of the sports club Vimpelin Veto: its films
 * page has one `div.elokuva` per film, with labelled facts ("Näytökset:", "Kesto:",
 * "Liput:", "Ikäraja:") and the shows written freehand: "la 31.10. klo 15 ja su 1.11 klo
 * 18", "ke 4.11. ja to 5.11. klo 18". Films without shows stay on the page with an empty
 * "Näytökset:". Read 2026-10-30; found through elokuviin.com.
 */
export const NuorisokuvatSite = SiteBase.extend({
  /** The page with the programme. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type NuorisokuvatSite = z.infer<typeof NuorisokuvatSite>;

export const NUORISOKUVAT_SITES: NuorisokuvatSite[] = defineSites(NuorisokuvatSite, [
  {
    provider: "nuorisokuvat",
    name: "Vimpelin Nuorisokuvat",
    homepage: "https://vimpelinveto.fi/elokuvat",
    programme: "https://vimpelinveto.fi/elokuvat",
    verifiedAt: "2026-10-30",
    notes:
      "Address from the cinema's contact page (/elokuvat/yhteystiedot). Tickets at the youth centre before the show, or in advance at Vimpelin Veto's office.",
    venues: [
      {
        slug: "vimpeli",
        name: "Vimpelin Nuorisokuvat",
        city: "Vimpeli",
        address: "Patruunantie 12",
        postalCode: "62800",
        geo: { lat: 63.159693, lon: 23.824323 },
        geoSource: "osm:way/179169786",
      },
    ],
  },
]);
