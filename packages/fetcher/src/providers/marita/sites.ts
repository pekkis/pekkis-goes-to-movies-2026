import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Elokuvateatteri Marita's front page: the `#show-times` module has one `.movie-info` block
 * per screening, with the date and its year, the time, the price, the spoken language and
 * the age-limit image. Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/marita.py,
 * AGPL-3.0); re-verified 2026-10-15.
 */
export const MaritaSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type MaritaSite = z.infer<typeof MaritaSite>;

export const MARITA_SITES: MaritaSite[] = defineSites(MaritaSite, [
  {
    provider: "marita",
    name: "Elokuvateatteri Marita",
    homepage: "https://elokuvateatterimarita.fi",
    verifiedAt: "2026-10-15",
    notes: "Address from the cinema's page and OSM (Koulukatu 1, 83500 Outokumpu), 2026-10-15.",
    venues: [
      {
        slug: "outokumpu",
        name: "Elokuvateatteri Marita",
        city: "Outokumpu",
        address: "Koulukatu 1",
        postalCode: "83500",
        geo: { lat: 62.7258599, lon: 29.016521 },
        geoSource: "osm:node/7202242999",
      },
    ],
  },
]);
