import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Engel's WordPress front page, where a plugin renders the Johku schedule on the
 * cinema's own server: one block per day (`#rsj_YYYY-MM-DD`), one row per screening
 * linking the film's page, where tickets are bought. Johku and its key are never touched.
 * The site challenges datacenter addresses with a captcha (SiteGround), so it is read
 * from a home connection only. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/engel.py, AGPL-3.0); re-verified 2026-10-14.
 */
export const EngelSite = SiteBase.extend({
  /** The site root, whose front page carries the programme. */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type EngelSite = z.infer<typeof EngelSite>;

export const ENGEL_SITES: EngelSite[] = defineSites(EngelSite, [
  {
    provider: "kinoengel",
    name: "Kino Engel",
    homepage: "https://kinoengel.fi",
    base: "https://kinoengel.fi",
    verifiedAt: "2026-10-14",
    titlePrefixes: {
      Barnsöndagar: { series: "Barnsöndagar", tags: ["kids"] },
      KesäKino: { series: "KesäKino" },
    },
    notes: "Address from the cinema's own page (Sofiankatu 4), 2026-10-14.",
    venues: [
      {
        slug: "helsinki",
        name: "Kino Engel",
        city: "Helsinki",
        address: "Sofiankatu 4",
        postalCode: "00170",
        geo: { lat: 60.1686498, lon: 24.9519931 },
        geoSource: "osm:node/2493674692",
      },
    ],
  },
]);
