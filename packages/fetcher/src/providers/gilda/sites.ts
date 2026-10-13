import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Gilda (Helsinki): a MyCloudCinema cinema whose site reads its own WordPress facade.
 * Venues split by screen: one MyCloudCinema cinema (15) holds Gilda's three screens and
 * the separate Bio Rex Lasipalatsi house. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/gilda.py, AGPL-3.0); re-verified 2026-10-13.
 */
export const GildaVenue = SiteVenue.extend({
  /** The MyCloudCinema `cinema_screen_id`s this venue owns. */
  screens: z.array(z.number().int()).min(1),
});

export const GildaSite = SiteBase.extend({
  /** The WordPress root, e.g. https://www.gilda.fi. */
  base: z.url(),
  /** The programme page: where a show goes when its film has no page of its own. */
  programmePath: z.string().startsWith("/"),
  venues: z.array(GildaVenue).min(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type GildaSite = z.infer<typeof GildaSite>;

export const GILDA_SITES: GildaSite[] = defineSites(GildaSite, [
  {
    provider: "gilda",
    name: "Gilda",
    homepage: "https://www.gilda.fi",
    base: "https://www.gilda.fi",
    programmePath: "/elokuvat/",
    verifiedAt: "2026-10-13",
    titlePrefixes: {
      // States the format only; the row's version_70mm flag carries it.
      "70mm": {},
      "Pieni elokuvakerho": { series: "Pieni elokuvakerho" },
    },
    venues: [
      {
        slug: "kamppi",
        name: "Gilda",
        city: "Helsinki",
        address: "Narinkka 2",
        postalCode: "00100",
        geo: { lat: 60.169977, lon: 24.935552 },
        geoSource: "osm:node/11701088977",
        screens: [66, 67, 68],
      },
      {
        slug: "lasipalatsi",
        name: "Bio Rex Lasipalatsi",
        city: "Helsinki",
        address: "Mannerheimintie 22-24",
        postalCode: "00100",
        geo: { lat: 60.17059, lon: 24.936016 },
        geoSource: "osm:node/1381017800",
        screens: [69],
      },
    ],
  },
]);
