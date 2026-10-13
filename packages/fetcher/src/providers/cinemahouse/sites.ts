import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Cinemas on the WordPress `cinema-reservations` plugin (the "cinemahouse" theme). The
 * front page renders the whole programme: film tiles (rating, runtime, genres) and one
 * row per screening (date without a year, time, hall, price, free seats, the reservation
 * link). One request per site. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/cinemahouse.py, AGPL-3.0); re-verified 2026-10-13.
 */
export const CinemahouseSite = SiteBase.extend({
  /** The site root, whose front page carries the programme. */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type CinemahouseSite = z.infer<typeof CinemahouseSite>;

const V = "2026-10-13";

export const CINEMAHOUSE_SITES: CinemahouseSite[] = defineSites(CinemahouseSite, [
  {
    provider: "kinopiispanristi",
    name: "Kino Piispanristi",
    homepage: "https://www.kinopiispanristi.fi",
    base: "https://www.kinopiispanristi.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "kaarina",
        name: "Kino Piispanristi",
        city: "Kaarina",
        address: "Jännekatu 2",
        postalCode: "20760",
        geo: { lat: 60.414849, lon: 22.32768 },
        geoSource: "osm:node/4738247767",
      },
    ],
  },
  {
    provider: "kinolumo",
    name: "Kino Lumo",
    homepage: "https://www.kinolumo.fi",
    base: "https://www.kinolumo.fi",
    verifiedAt: V,
    notes: "OSM names it Elokuvateatteri Lumo, at the cinema's own address.",
    venues: [
      {
        slug: "salo",
        name: "Kino Lumo",
        city: "Salo",
        address: "Savipajankatu 2B",
        postalCode: "24260",
        geo: { lat: 60.395913, lon: 23.127812 },
        geoSource: "osm:node/8240833887",
      },
    ],
  },
  {
    provider: "laitilankino",
    name: "Laitilan Kino",
    homepage: "https://www.laitilankino.fi",
    base: "https://www.laitilankino.fi",
    verifiedAt: V,
    venues: [
      {
        slug: "laitila",
        name: "Laitilan Kino",
        city: "Laitila",
        geo: { lat: 60.879182, lon: 21.695557 },
        geoSource: "osm:node/14047635661",
      },
    ],
  },
]);
