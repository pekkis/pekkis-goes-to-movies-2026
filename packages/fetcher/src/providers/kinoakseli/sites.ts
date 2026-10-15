import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Akseli's Elementor front page: per film, its facts ("Ikäraja : 12", "Liput : 14€")
 * come before its heading and its screenings ("Näytösajat To 15.10. klo 17:45") after it.
 * No year; tickets at the door. The site challenges datacenter addresses (SiteGround), so
 * it is read from a home connection only. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/kinoakseli.py, AGPL-3.0); re-verified 2026-10-15.
 */
export const KinoAkseliSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KinoAkseliSite = z.infer<typeof KinoAkseliSite>;

export const KINOAKSELI_SITES: KinoAkseliSite[] = defineSites(KinoAkseliSite, [
  {
    provider: "kinoakseli",
    name: "Kino Akseli",
    homepage: "https://kinoakseli.fi",
    verifiedAt: "2026-10-15",
    notes: "Address from the cinema's page and OSM (Vihdintie 4-6, 03100 Nummela), 2026-10-15.",
    venues: [
      {
        slug: "nummela",
        name: "Kino Akseli",
        city: "Nummela",
        address: "Vihdintie 4-6",
        postalCode: "03100",
        geo: { lat: 60.3354507, lon: 24.3202742 },
        geoSource: "osm:node/8193549402",
      },
    ],
  },
]);
