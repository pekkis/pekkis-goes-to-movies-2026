import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Visio (Vuokatti, Sotkamo): the WordPress (Elementor) front page has the week's
 * programme as paragraphs, one per day: "PERJANTAI 30.10." in bold, then a line per show
 * "18:00 Late Lammas-elokuva: hämäräpuuhissa (7) – ensi-ilta!" with the title linking the
 * film's page. Talks with filmmakers are lines of their own ("KLAUS HÄRÖ – Keskustelu
 * elokuvasta Ei koskaan yksin"). Read 2026-10-30; found through elokuviin.com.
 */
export const KinoVisioSite = SiteBase.extend({
  /** The page with the programme. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
  /** Site-specific notes after the title ("huom! ikäraja"), merged over LABELS. */
  labels: z.record(z.string(), LabelRule).optional(),
});
export type KinoVisioSite = z.infer<typeof KinoVisioSite>;

export const KINOVISIO_SITES: KinoVisioSite[] = defineSites(KinoVisioSite, [
  {
    provider: "kinovisio",
    name: "Kino Visio",
    homepage: "https://www.kinovisio.net",
    programme: "https://www.kinovisio.net/",
    verifiedAt: "2026-10-30",
    titlePrefixes: { LEFFAKLUBI: { series: "Leffaklubi" } },
    labels: {
      // A reminder that the age limit is higher than the audience might think.
      "huom! ikäraja": {},
      "toiseksi viimeinen näytös": {},
      "toiseksi viimeinen esitys": {},
    },
    notes:
      "Run by Versova Puu ry. The Sotkamo cinema (Salmelantie) closed on 22.3.2026; the programme continues in Vuokatti, opened 18.11.2025. Address from the front page. Tickets in the lobby, reservations by phone.",
    venues: [
      {
        slug: "vuokatti",
        name: "Kino Visio Vuokatti",
        city: "Sotkamo",
        address: "Kidekuja 2",
        postalCode: "88610",
        // OSM's "Kino Visio" is the closed Sotkamo cinema; this is the address geocoded.
        geo: { lat: 64.141148, lon: 28.294366 },
        geoSource: "nominatim",
      },
    ],
  },
]);
