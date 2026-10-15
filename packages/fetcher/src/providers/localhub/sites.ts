import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Cinemas on a town's Localhub event calendar: its public search returns one page per
 * screening, filtered by a hashtag and checked against the "Movies / Cinema" category.
 * Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/localhub.py, AGPL-3.0);
 * re-verified 2026-10-15.
 */
export const LocalhubSite = SiteBase.extend({
  /** The calendar root. */
  base: z.url(),
  /** The calendar's collection id. */
  collection: z.string().regex(/^[0-9a-f]{24}$/),
  /** The search term, also required among a page's hashtags. */
  hashtag: z.string().min(1),
  /** The category a page must carry to be a screening. */
  category: z.string().min(1),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type LocalhubSite = z.infer<typeof LocalhubSite>;

export const LOCALHUB_SITES: LocalhubSite[] = defineSites(LocalhubSite, [
  {
    provider: "kinoakustiikka",
    name: "Kino Akustiikka",
    homepage: "http://www.kinoakustiikka.fi",
    base: "https://tapahtumat.ylivieska.fi",
    collection: "65b0e6fdfd13b97001a1b35d",
    hashtag: "kinoakustiikka",
    category: "Movies / Cinema",
    verifiedAt: "2026-10-15",
    notes: "The town of Ylivieska's calendar; the cinema is in the culture centre Akustiikka.",
    venues: [
      {
        slug: "ylivieska",
        name: "Kino Akustiikka",
        city: "Ylivieska",
        address: "Koulukatu 2 B",
        postalCode: "84100",
        geo: { lat: 64.0709719, lon: 24.5283106 },
        geoSource: "osm:node/2507982005",
      },
    ],
  },
]);
