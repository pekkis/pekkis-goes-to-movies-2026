import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue, Slug } from "../sites.ts";

/**
 * Johku storefronts: cinemas whose site is a Johku shop (johku.com, a Finnish ticketing and
 * booking platform). Each storefront's own code reads its programme from
 * `https://{host}/api/{shop}/fi_FI/showschedule.json?category={n}…`, anonymously.
 *
 * Adding a cinema: the front page's `__NUXT_DATA__` names `storefront-{shop}-fi_FI` and one
 * `showschedule-fi_FI-f{date}-c{category}` key per programme block; list the film blocks.
 * Not here: sites that only embed a Johku widget (Kino Engel, Kino Tapiola) or load the
 * show list through `/api/auth/widget-session` (KuvaTähti): those need an API key.
 *
 * Origin: Leffavuoro (vendor/leffavuoro/scripts/providers/johku.py), which reads the copy
 * embedded in the front page; the endpoint itself was first called here, 2026-10-12.
 */

export const JohkuVenue = SiteVenue.extend({
  /** The hall's `resource_name` in the schedule. */
  resource: z.string().min(1),
});
export type JohkuVenue = z.infer<typeof JohkuVenue>;

export const JohkuSite = SiteBase.extend({
  /** Storefront host the API answers on ("www.biomarilyn.com"). */
  host: z.string().regex(/^[a-z0-9.-]+$/),
  shop: Slug,
  /** Programme blocks with films (not theatre, not hall hire). */
  categories: z.array(z.number().int().positive()).min(1),
  venues: z.array(JohkuVenue).min(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type JohkuSite = z.infer<typeof JohkuSite>;

export const scheduleUrl = (site: JohkuSite) =>
  `https://${site.host}/api/${site.shop}/fi_FI/showschedule.json`;

const V = "2026-10-12";

export const JOHKU_SITES: JohkuSite[] = defineSites(JohkuSite, [
  {
    provider: "biomarilyn",
    name: "Bio Marilyn",
    homepage: "https://www.biomarilyn.com",
    host: "www.biomarilyn.com",
    shop: "biomarilyn",
    categories: [1, 9],
    verifiedAt: V,
    notes:
      "Two blocks (now showing, coming soon) that share some shows; film links are on biomarilyn.johku.com.",
    venues: [
      {
        slug: "lapua",
        name: "Bio Marilyn",
        city: "Lapua",
        resource: "Bio Marilyn",
        address: "Vanhan paukun tie 1",
        postalCode: "62100",
        geo: { lat: 62.968085, lon: 23.017527 },
        geoSource: "osm:node/194555639",
      },
    ],
  },
  {
    provider: "vihdinkino",
    name: "Vihdin Kino",
    homepage: "https://vihdinkino.fi",
    host: "vihdinkino.fi",
    shop: "vihdinkino",
    categories: [9],
    verifiedAt: V,
    titlePrefixes: { "MLL-näytös": { series: "MLL-näytös", tags: ["kids"] } },
    venues: [
      {
        slug: "vihti",
        name: "Vihdin Kino",
        city: "Vihti",
        resource: "Vihdin Kino",
        address: "Riihitie 2",
        postalCode: "03400",
        geo: { lat: 60.419193, lon: 24.316843 },
        geoSource: "osm:node/852779001",
      },
    ],
  },
  {
    provider: "bioforum",
    name: "Bio Forum",
    homepage: "https://bioforum.fi",
    host: "bioforum.fi",
    shop: "bioforum",
    categories: [9],
    verifiedAt: V,
    venues: [
      {
        slug: "tammisaari",
        name: "Bio Forum",
        city: "Raasepori",
        shortName: "Bio Forum Tammisaari",
        resource: "Bio Forum",
        address: "Helene Schjerfbecks gata 5",
        geo: { lat: 59.973495, lon: 23.435663 },
        geoSource: "osm:node/1396819513",
      },
    ],
  },
  {
    provider: "kinokulma",
    name: "Kinokulma",
    homepage: "https://kinokulma.fi",
    host: "kinokulma.fi",
    shop: "kinokulma",
    categories: [1],
    verifiedAt: V,
    notes:
      'Lists hall hire ("Salivaraus"), closures ("Olemme vapaalla") and private bookings too; they have no price, age limit or language and are left out.',
    venues: [
      {
        slug: "oulainen",
        name: "Kinokulma",
        city: "Oulainen",
        resource: "Kulmasali",
        address: "Asemakatu 1",
        geo: { lat: 64.269778, lon: 24.819202 },
        geoSource: "osm:node/5437298938",
      },
    ],
  },
  {
    provider: "kinohannikainen",
    name: "Kino Hannikainen",
    homepage: "https://www.kinohannikainen.net",
    host: "www.kinohannikainen.net",
    shop: "kinohannikainen",
    categories: [6],
    verifiedAt: V,
    venues: [
      {
        slug: "nurmes",
        name: "Kino Hannikainen",
        city: "Nurmes",
        resource: "Hannikaisen sali",
        address: "Kötsintie 2",
        postalCode: "75500",
        geo: { lat: 63.549298, lon: 29.12749 },
        geoSource: "osm:node/565563436",
      },
    ],
  },
  {
    provider: "kinovirta",
    name: "Kino Virta",
    homepage: "https://kinovirta.johku.com",
    host: "kinovirta.johku.com",
    shop: "kinovirta",
    categories: [2],
    verifiedAt: V,
    notes: "No storefront domain of its own; virtasali.fi links here.",
    venues: [
      {
        slug: "kalajoki",
        name: "Kino Virta",
        city: "Kalajoki",
        resource: "Virta-sali",
        geo: { lat: 64.259867, lon: 23.946979 },
        geoSource: "osm:node/5923100732",
      },
    ],
  },
  {
    provider: "kulttuurimylly",
    name: "Kulttuurimylly",
    homepage: "https://kulttuurimylly.johku.com",
    host: "kulttuurimylly.johku.com",
    shop: "kulttuurimylly",
    categories: [2],
    verifiedAt: V,
    notes:
      'Block 5 is theatre ("Feeniks-sali (Teatteri)"), not read. The point is the mill complex at ' +
      "Jauhokuja 3 (Nominatim gives the Liikuntamylly building; Kulttuurimylly is 3 A1 / C).",
    venues: [
      {
        slug: "myllypuro",
        name: "Kino Kulttuurimylly",
        city: "Helsinki",
        resource: "Feeniks-sali (Kino Kulttuurimylly)",
        address: "Jauhokuja 3",
        postalCode: "00920",
        geo: { lat: 60.224767, lon: 25.07714 },
        geoSource: "nominatim",
      },
    ],
  },
]);
