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
 * A venue page that shows a category shared from another shop ("Ohjelmisto", Sun Kino's and
 * KuvaTähti's venue pages) reads the same call with the sharing shop and that category.
 * Not here: sites that only embed a Johku widget for tickets (Kino Engel, Kino Tapiola).
 *
 * Origin: Leffavuoro (vendor/leffavuoro/scripts/providers/johku.py), which reads the copy
 * embedded in the front page; the endpoint itself was first called here, 2026-10-12.
 */

export const JohkuVenue = SiteVenue.extend({
  /** Its halls' `resource_name`s in the schedule; the first is the venue's source id. */
  resources: z.array(z.string().min(1)).min(1),
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
        resources: ["Bio Marilyn"],
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
        resources: ["Vihdin Kino"],
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
        resources: ["Bio Forum"],
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
        resources: ["Kulmasali"],
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
        resources: ["Hannikaisen sali"],
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
        resources: ["Virta-sali"],
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
        resources: ["Feeniks-sali (Kino Kulttuurimylly)"],
        address: "Jauhokuja 3",
        postalCode: "00920",
        geo: { lat: 60.224767, lon: 25.07714 },
        geoSource: "nominatim",
      },
    ],
  },
  {
    provider: "sunkino",
    name: "Sun Kino",
    homepage: "https://elokuviin.info",
    host: "elokuviin.info",
    shop: "elokuviin",
    categories: [2],
    verifiedAt: "2026-10-30",
    notes:
      'Sun Kino Oy\'s storefront for four cinemas (Kauhavan Y-Kino has its own shop). Each venue page shows the category "Ohjelmisto" (2) shared into the shop "elokuviin", which answers the anonymous schedule call with all four. Thought to need the widget key until 2026-10-30 (Leffavuoro tried allproducts.json).',
    venues: [
      {
        slug: "kauhava",
        name: "Y-Kino",
        city: "Kauhava",
        resources: ["Y-Kino (KAUHAVA)"],
        address: "Kauppatie 109",
        postalCode: "62200",
        geo: { lat: 63.09942, lon: 23.05971 },
        geoSource: "osm:node/6236693231",
      },
      {
        slug: "alavus",
        name: "Kino Kyntäjä",
        city: "Alavus",
        resources: ["Kino Kyntäjä, sali 1 (ALAVUS)", "Kino Kyntäjä, sali 2 (ALAVUS)"],
        address: "Järviluomantie 5",
        postalCode: "63300",
        geo: { lat: 62.585566, lon: 23.615868 },
        geoSource: "osm:node/2638781636",
      },
      {
        slug: "ahtari",
        name: "Sun Kino",
        city: "Ähtäri",
        resources: ["Sun Kino (ÄHTÄRI)"],
        address: "Lukiontie 3",
        postalCode: "63700",
        geo: { lat: 62.551206, lon: 24.077192 },
        geoSource: "osm:node/11384636630",
      },
      {
        slug: "alajarvi",
        name: "Alareksi",
        city: "Alajärvi",
        resources: ["Alareksi (ALAJÄRVI)"],
        geo: { lat: 62.999335, lon: 23.81868 },
        geoSource: "osm:node/2992011001",
      },
    ],
  },
  {
    provider: "kuvatahti",
    name: "Kuva-Tähti",
    homepage: "https://www.kuvatahti.fi",
    host: "www.kuvatahti.fi",
    shop: "kuvatahti",
    categories: [2],
    verifiedAt: "2026-10-30",
    notes:
      'Kuva-Tähti Oy\'s storefront for Kuvala and Kauttuan Kuva. As with Sun Kino, the venue pages show the shared category "Ohjelmisto" (2), read anonymously; thought to need the widget key until 2026-10-30.',
    venues: [
      {
        slug: "uusikaupunki",
        name: "Kuvala",
        city: "Uusikaupunki",
        resources: ["Kuvala (UUSIKAUPUNKI)"],
        geo: { lat: 60.800592, lon: 21.417702 },
        geoSource: "osm:node/4408430758",
      },
      {
        slug: "eura",
        name: "Kauttuan Kuva",
        city: "Eura",
        resources: ["Kauttuan Kuva sali 1 (EURA)", "Kauttuan Kuva sali 2 (EURA)"],
        geo: { lat: 61.114852, lon: 22.167567 },
        geoSource: "osm:node/551331489",
      },
    ],
  },
]);
