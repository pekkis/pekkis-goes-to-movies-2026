import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Programmes typed freehand by one author: Movie Company Alatalo's touring cinema (a town
 * heading per venue) and Elokuvateatteri Huvimylly in Raahe (one venue). Lines are date
 * headings ("Lauantaina 17.10"), rows ("Klo 14.00 Lapin Sota -k16/13-", "16.30 …") and
 * title continuations closed by a rating marker. Tickets at the door, cash. Mapped by
 * Leffavuoro (Shady-Dev/kino, scripts/providers/alatalo.py and huvimylly.py, AGPL-3.0);
 * re-verified 2026-10-15.
 */
export const AlataloVenue = SiteVenue.extend({
  /** The first word(s) of this venue's heading line ("Pudasjärvi"); absent: the only venue. */
  heading: z.string().min(1).optional(),
});

export const AlataloSite = SiteBase.extend({
  /** Where the programme is: a page's HTML, or a WordPress page's rendered content. */
  source: z.discriminatedUnion("kind", [
    z.object({ kind: z.literal("html"), url: z.url() }),
    z.object({ kind: z.literal("wp-page"), url: z.url() }),
  ]),
  /** The page's one ticket price ("Liput elokuviin vain10-€"), its amount captured. */
  pricePattern: z.string().optional(),
  venues: z.array(AlataloVenue).min(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type AlataloSite = z.infer<typeof AlataloSite>;

export const ALATALO_SITES: AlataloSite[] = defineSites(AlataloSite, [
  {
    provider: "alatalo",
    name: "Movie Company Alatalo",
    homepage: "http://www.moviecompanyalatalo.fi",
    // HTTP only: the host refuses 443 (Leffavuoro, 2026-09-19).
    source: { kind: "html", url: "http://www.moviecompanyalatalo.fi/" },
    pricePattern: "Liput elokuviin vain\\s*(\\d{1,3})\\s*-?\\s*€",
    verifiedAt: "2026-10-15",
    notes:
      "A touring operator in northern Finland. Town headings name the hall; OSM lists only Kemijärvi's. Addresses of Pudasjärvi, Haapajärvi and Kiuruvesi from the maintainer (2026-10-16), coordinates from OSM's buildings at them.",
    venues: [
      {
        slug: "pudasjarvi",
        name: "Pohjantähti (Alatalo)",
        city: "Pudasjärvi",
        heading: "Pudasjärvi",
        address: "Teollisuustie 1",
        postalCode: "93100",
        geo: { lat: 65.343395, lon: 26.967724 },
        geoSource: "osm:way/491511299",
      },
      {
        slug: "haapajarvi",
        name: "Teatterisali (Alatalo)",
        city: "Haapajärvi",
        heading: "Haapajärvi",
        // The same address as the town library, whose OSM node it is.
        address: "Kauppakatu 19",
        postalCode: "85800",
        geo: { lat: 63.749783, lon: 25.314609 },
        geoSource: "osm:node/245268824",
      },
      {
        slug: "kiuruvesi",
        name: "Kiurusali (Alatalo)",
        city: "Kiuruvesi",
        heading: "Kiuruvesi",
        // The event hall of Kiuruvesi's culture house; OSM's building at the address.
        address: "Lähteentie 10 A",
        postalCode: "74700",
        geo: { lat: 63.648359, lon: 26.619174 },
        geoSource: "osm:way/182678139",
      },
      {
        slug: "kemijarvi",
        name: "Kemijärven kulttuurikeskus (Alatalo)",
        city: "Kemijärvi",
        heading: "Kemijärvi",
        address: "Hietaniemenkatu 5",
        postalCode: "98100",
        geo: { lat: 66.7155184, lon: 27.4232902 },
        geoSource: "osm:way/221824429",
      },
    ],
  },
  {
    provider: "huvimylly",
    name: "Elokuvateatteri Huvimylly",
    homepage: "https://www.huvimylly.com",
    // The front page's content through WordPress's REST route (a tenth of the page).
    source: {
      kind: "wp-page",
      url: "https://www.huvimylly.com/wp-json/wp/v2/pages?slug=etusivu&_fields=content",
    },
    pricePattern: "Liput vain\\s*(\\d{1,3})\\s*-?\\s*€",
    verifiedAt: "2026-10-15",
    notes: "In the Tapahtumatalo's Raahesali hall, Raahe; OSM node for Raahesali.",
    venues: [
      {
        slug: "raahe",
        name: "Elokuvateatteri Huvimylly",
        city: "Raahe",
        postalCode: "92100",
        geo: { lat: 64.6849464, lon: 24.4799451 },
        geoSource: "osm:node/8827057758",
      },
    ],
  },
]);
