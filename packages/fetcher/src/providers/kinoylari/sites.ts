import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Yläri (Kittilä): the municipality's cinema page. Below the "Ohjelmisto" heading each
 * screening is one block: "to 15.10. klo 15.00 <strong>Title</strong> K7". Read 2026-10-16;
 * found through nytleffaan.fi's directory.
 */
export const KinoYlariSite = SiteBase.extend({
  /** The municipality's page for the cinema. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KinoYlariSite = z.infer<typeof KinoYlariSite>;

export const KINOYLARI_SITES: KinoYlariSite[] = defineSites(KinoYlariSite, [
  {
    provider: "kinoylari",
    name: "Kino Yläri",
    homepage: "https://kittila.fi/kulttuuri-ja-vapaa-aika/kulttuuri/elokuvat-kino-ylari",
    programme: "https://kittila.fi/kulttuuri-ja-vapaa-aika/kulttuuri/elokuvat-kino-ylari",
    verifiedAt: "2026-10-16",
    notes:
      "Shows in the auditorium of Kittilä's lower secondary school (the page), OSM's Kittilän yläkoulu (Valtatie 9A). Tickets at the door, advance tickets at the municipal office.",
    venues: [
      {
        slug: "kittila",
        name: "Kino Yläri",
        city: "Kittilä",
        address: "Valtatie 9A",
        postalCode: "99100",
        geo: { lat: 67.6503187, lon: 24.9100535 },
        geoSource: "osm:way/1350375603",
      },
    ],
  },
]);
