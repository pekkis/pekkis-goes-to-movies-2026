import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * The "kinomaatti" WordPress plugin's timetable: one `tr.tulossa-movie` per screening, with
 * the film link and title (`a.tulossa-movie-name h3`, the age as an image file
 * `kino-age-12`, the format as `span.tyyppi`), `.tulossa-esitysaika` ("keskiviikko, 21.10.
 * klo 18.00") and `.tulossa-hinta` ("13.50 €"). Read 2026-10-16 (Kino Jalasjärvi); found
 * through nytleffaan.fi's directory.
 */
export const KinomaattiSite = SiteBase.extend({
  /** The page with the timetable. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KinomaattiSite = z.infer<typeof KinomaattiSite>;

export const KINOMAATTI_SITES: KinomaattiSite[] = defineSites(KinomaattiSite, [
  {
    provider: "kinojalasjarvi",
    name: "Kino Jalasjärvi",
    homepage: "https://kinojalasjarvi.fi",
    programme: "https://kinojalasjarvi.fi/",
    verifiedAt: "2026-10-16",
    notes:
      "Jalasjärvi is part of Kurikka since 2016. Address from nytleffaan.fi's directory (Keskustie 43, 61600 Jalasjärvi), geocoded with Nominatim (the address point; OSM names no cinema there). The site sells no tickets online; screenings link to the film's page.",
    venues: [
      {
        slug: "jalasjarvi",
        name: "Kino Jalasjärvi",
        city: "Kurikka",
        address: "Keskustie 43",
        postalCode: "61600",
        geo: { lat: 62.4865875, lon: 22.7656299 },
        geoSource: "nominatim",
      },
    ],
  },
]);
