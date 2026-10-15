import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Kuusamotalo's WordPress: one post per film, read through the public REST route.
 * A film post carries its facts ("-S-", "Kesto 1h 28min", "Liput 12€") and an
 * "Esitysajat:" list ("Ke 14.10. klo 15 ja 19"); notices carry none. Mapped by Leffavuoro
 * (Shady-Dev/kino, scripts/providers/kuusamotalo.py, AGPL-3.0); re-verified 2026-10-15.
 */
export const KuusamotaloSite = SiteBase.extend({
  /** The WordPress root; posts are `{base}/wp-json/wp/v2/posts`. */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KuusamotaloSite = z.infer<typeof KuusamotaloSite>;

export const KUUSAMOTALO_SITES: KuusamotaloSite[] = defineSites(KuusamotaloSite, [
  {
    provider: "kuusamotalo",
    name: "Kino Kuusamotalo",
    homepage: "https://kinokuusamotalo.fi",
    base: "https://kinokuusamotalo.fi",
    verifiedAt: "2026-10-15",
    notes: "Address from the cinema's page (Kaarlo Hännisen tie 2, 93600 Kuusamo), 2026-10-15.",
    venues: [
      {
        slug: "kuusamo",
        name: "Kino Kuusamotalo",
        city: "Kuusamo",
        address: "Kaarlo Hännisen tie 2",
        postalCode: "93600",
        geo: { lat: 65.9701615, lon: 29.1751849 },
        geoSource: "osm:way/167231017",
      },
    ],
  },
]);
