import { z } from "zod";
import { COMMON_TITLE_PREFIXES, LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Nexxo Scope (a WordPress plugin) sites. Adding a cinema = adding an entry here.
 *
 * Before trusting a new entry, verify it as a visitor would (see docs/data-sources.md):
 * - ask the API for its `locationId` (ids are not guessable; one host can serve several
 *   cinemas, and a cinema's data can live on another host's API),
 * - open the built programme link and check it shows the plugin's showlist.
 *
 * Origin: Leffavuoro (vendor/leffavuoro/scripts/providers/nexxo.py), re-verified 2026-10-10.
 */

/**
 * How a `showTypeTitle` maps onto the model. Unknown titles become `series` (festival and
 * series names are what the field mostly carries), so nothing is lost.
 * - `{}`: ignore (regular screening, or a label only meaningful inside the cinema)
 * - `tags`: screening tags; `event: true` also marks the film listing as an event
 */
export const ShowTypeRule = LabelRule;
export type ShowTypeRule = LabelRule;

/** Platform defaults; a site's `showTypes` overrides or extends them. */
export const DEFAULT_SHOW_TYPES: Record<string, ShowTypeRule> = {
  "Tavallinen näytös": {},
  "Viikko-ohjelmisto": {},
  Konsertti: { tags: ["event-cinema"], event: true },
  Taikashow: { tags: ["event-cinema"], event: true },
  "Muut tapahtumat": { tags: ["event-cinema"], event: true },
};

/** "Prefix: Title" labels: the shared rules (labels.ts), extended per site. */
export const TitlePrefixRule = LabelRule;
export type TitlePrefixRule = LabelRule;
export const DEFAULT_TITLE_PREFIXES: Record<string, LabelRule> = COMMON_TITLE_PREFIXES;

export const NexxoVenue = SiteVenue.extend({
  /** The plugin's `locationid`. Several venues may share one. */
  locationId: z.string().regex(/^\d+$/),
  /** When venues share a location, the `roomId`s this venue owns (Kino Metso's towns). */
  roomIds: z.array(z.string().regex(/^\d+$/)).optional(),
  /** A page of its own, already filtered to this venue; replaces programme?location=N. */
  page: z.string().startsWith("/").optional(),
});
export type NexxoVenue = z.infer<typeof NexxoVenue>;

export const NexxoSite = SiteBase.extend({
  /** Host whose API serves the data, if not the homepage (Bio Säde reads kinohirvi.fi's). */
  apiBase: z.url().optional(),
  /** Programme page the screening links point to, e.g. "/naytokset/" (differs per site). */
  programmePath: z.string().startsWith("/"),
  venues: z.array(NexxoVenue).min(1),
  /** Site-specific showTypeTitle rules, merged over DEFAULT_SHOW_TYPES. */
  showTypes: z.record(z.string(), ShowTypeRule).optional(),
  /** Site-specific title prefix rules (without the colon), merged over the defaults. */
  titlePrefixes: z.record(z.string(), TitlePrefixRule).optional(),
});
export type NexxoSite = z.infer<typeof NexxoSite>;

export const NEXXO_SITES: NexxoSite[] = defineSites(NexxoSite, [
  {
    provider: "kinoset",
    name: "Kinoset",
    homepage: "https://kinoset.fi",
    programmePath: "/ohjelmisto/",
    verifiedAt: "2026-10-10",
    venues: [
      {
        slug: "huittinen",
        locationId: "1",
        name: "Kino 1-2",
        city: "Huittinen",
        address: "Sahakatu 2",
        postalCode: "32700",
        geo: { lat: 61.180046, lon: 22.716464 },
        geoSource: "nominatim",
      },
      {
        slug: "loimaa",
        locationId: "2",
        name: "Kinema",
        city: "Loimaa",
        address: "Vesikoskenkatu 21",
        postalCode: "32200",
        geo: { lat: 60.85288, lon: 23.055499 },
        geoSource: "osm:node/10984353704",
      },
      {
        slug: "sastamala",
        locationId: "3",
        name: "Bio Sastamala",
        city: "Sastamala",
        address: "Puistokatu 32",
        postalCode: "38200",
        geo: { lat: 61.338068, lon: 22.917104 },
        geoSource: "osm:node/287019356",
      },
    ],
  },
  {
    provider: "kinoaurora",
    name: "Kino Aurora",
    homepage: "https://kinoaurora.fi",
    programmePath: "/naytokset/",
    verifiedAt: "2026-10-10",
    titlePrefixes: {
      Filminäytös: { series: "Filminäytös" },
      Minikino: { series: "Minikino", tags: ["kids"] },
    },
    venues: [
      {
        slug: "jyvaskyla",
        locationId: "1",
        name: "Kino Aurora",
        city: "Jyväskylä",
        address: "Seminaarinkatu 13",
        postalCode: "40100",
        geo: { lat: 62.236603, lon: 25.734976 },
        geoSource: "osm:node/14270115364",
      },
    ],
  },
  {
    provider: "kinohirvi",
    name: "Kino Hirvi",
    homepage: "https://kinohirvi.fi",
    programmePath: "/",
    verifiedAt: "2026-10-10",
    venues: [
      {
        slug: "aanekoski",
        locationId: "2",
        name: "Kino Hirvi",
        city: "Äänekoski",
        address: "Kotakennääntie 9",
        postalCode: "44100",
        geo: { lat: 62.601517, lon: 25.72161 },
        geoSource: "osm:node/2184338692",
      },
    ],
  },
  {
    provider: "biosade",
    name: "Bio Säde",
    homepage: "https://www.biosade.fi",
    apiBase: "https://kinohirvi.fi",
    programmePath: "/",
    verifiedAt: "2026-10-10",
    notes: "biosade.fi's own API is empty; its front page calls kinohirvi.fi's API for location 4.",
    venues: [
      {
        slug: "mantta",
        locationId: "4",
        name: "Bio Säde",
        city: "Mänttä",
        geo: { lat: 62.031704, lon: 24.626281 },
        geoSource: "osm:node/6791996771",
      },
    ],
  },
  // Kino Marilyn (Loviisa) moved to eTiketti by 2026-10-24: see etiketti/sites.ts.
  {
    provider: "kinoolympia",
    name: "Kino Olympia",
    homepage: "https://kino-olympia.fi",
    programmePath: "/naytokset/",
    verifiedAt: "2026-10-10",
    venues: [
      {
        slug: "hanko",
        locationId: "1",
        name: "Kino Olympia",
        city: "Hanko",
        geo: { lat: 59.8249, lon: 22.967539 },
        geoSource: "osm:node/357239399",
      },
    ],
  },
  {
    provider: "jarvelankino",
    name: "Järvelän Kino",
    homepage: "https://jarvelankino.fi",
    programmePath: "/naytoslista/",
    // A comedy night in the cinema, not a film (2026-10-31).
    titlePrefixes: { "Järvelän Kinon Stand Up -ilta": { event: true } },
    verifiedAt: "2026-10-10",
    venues: [
      {
        slug: "jarvela",
        locationId: "1",
        name: "Järvelän Kino",
        city: "Kärkölä",
        address: "Hähkäniementie 16",
        postalCode: "16600",
        geo: { lat: 60.866439, lon: 25.26818 },
        geoSource: "osm:way/148579739",
      },
    ],
  },
  {
    provider: "kinometso",
    name: "Kino Metso",
    homepage: "https://ksek.fi",
    apiBase: "https://kinoaurora.fi",
    programmePath: "/kino-metso/",
    verifiedAt: "2026-10-10",
    notes:
      "KSEK's touring cinema: one location whose rooms are towns. Data from kinoaurora.fi " +
      "(same deployment as ksek.fi); each town has its own page. Riihivuori (room 21) is " +
      "folded into Muurame, which KSEK's site does too. Laukaa (24) and Viitasaari (10) " +
      "were found by the unclaimed-room warning, not in Leffavuoro's list; Toivakka (23) and " +
      "Hankasalmi (19) only once the fetch sent movieid=0 (2026-10-15). Each town " +
      "plays in a hall (address from its town page, geocoded with Nominatim); Viitasaari " +
      "plays at Nuorisotalon Teatteri (OSM: Viitasaaren teatteri), confirmed by the maintainer.",
    showTypes: { "Kino Metso": {}, "Kino Metso, kiinteähintainen": {} },
    titlePrefixes: { Minikino: { series: "Minikino", tags: ["kids"] } },
    venues: [
      {
        slug: "muurame",
        locationId: "2",
        roomIds: ["2", "21"],
        page: "/kino-metso/muurame/",
        name: "Kino Metso Muurame",
        city: "Muurame",
        address: "Nisulantie 1",
        postalCode: "40950",
        geo: { lat: 62.131357, lon: 25.669218 },
        geoSource: "nominatim",
      },
      {
        slug: "petajavesi",
        locationId: "2",
        roomIds: ["4"],
        page: "/kino-metso/petajavesi/",
        name: "Kino Metso Petäjävesi",
        city: "Petäjävesi",
        address: "Miilutie 4",
        postalCode: "41900",
        geo: { lat: 62.257816, lon: 25.180477 },
        geoSource: "nominatim",
      },
      {
        slug: "tikkakoski",
        locationId: "2",
        roomIds: ["11"],
        page: "/kino-metso/tikkakoski/",
        name: "Kino Metso Tikkakoski",
        city: "Jyväskylä",
        address: "Koulukatu 10",
        postalCode: "41160",
        geo: { lat: 62.393998, lon: 25.637795 },
        geoSource: "nominatim",
      },
      {
        slug: "vaajakoski",
        locationId: "2",
        roomIds: ["12"],
        page: "/kino-metso/vaajakoski/",
        name: "Kino Metso Vaajakoski",
        city: "Jyväskylä",
        address: "Savonmäentie 9",
        postalCode: "40800",
        geo: { lat: 62.24967, lon: 25.873522 },
        geoSource: "nominatim",
      },
      {
        slug: "laukaa",
        locationId: "2",
        roomIds: ["24"],
        page: "/kino-metso/laukaa/",
        name: "Kino Metso Laukaa",
        city: "Laukaa",
        address: "Saralinnantie 3",
        postalCode: "41340",
        geo: { lat: 62.416344, lon: 25.950415 },
        geoSource: "nominatim",
      },
      {
        slug: "viitasaari",
        locationId: "2",
        roomIds: ["10"],
        page: "/kino-metso/viitasaari/",
        name: "Kino Metso Viitasaari",
        city: "Viitasaari",
        address: "Koulukuja 8",
        postalCode: "44500",
        geo: { lat: 63.085083, lon: 25.84843 },
        geoSource: "osm:node/5940777731",
      },
      {
        slug: "toivakka",
        locationId: "2",
        roomIds: ["23"],
        page: "/kino-metso/toivakka/",
        name: "Kino Metso Toivakka",
        city: "Toivakka",
        address: "Iltaruskontie 4A",
        postalCode: "41660",
        geo: { lat: 62.0982807, lon: 26.0854837 },
        geoSource: "osm:node/559658460",
      },
      {
        slug: "hankasalmi",
        locationId: "2",
        roomIds: ["19"],
        page: "/kino-metso/hankasalmi/",
        name: "Kino Metso Hankasalmi",
        city: "Hankasalmi",
        address: "Kirkkotie 11",
        postalCode: "41520",
        geo: { lat: 62.38667, lon: 26.430363 },
        geoSource: "osm:way/186942567",
      },
    ],
  },
  {
    provider: "biosalo",
    name: "Bio-Salo",
    homepage: "https://biosalo.fi",
    programmePath: "/",
    verifiedAt: "2026-10-15",
    notes:
      "Plugin 25.051, which answers exportdailyshows only with `movieid` (the fetch sends 0). Location 1; location 2 is Bio Stara. Address from the cinema's info page (Helsingintie 11, Salo); OSM has the cinema node.",
    venues: [
      {
        slug: "salo",
        locationId: "1",
        page: "/",
        name: "Bio-Salo",
        city: "Salo",
        address: "Helsingintie 11",
        postalCode: "24260",
        geo: { lat: 60.3863219, lon: 23.134973 },
        geoSource: "osm:node/364359305",
      },
    ],
  },
  {
    provider: "biostara",
    name: "Bio Stara",
    homepage: "https://biostara.fi",
    apiBase: "https://biosalo.fi",
    programmePath: "/",
    verifiedAt: "2026-10-15",
    notes:
      "Bio-Salo's sister cinema: biostara.fi's widgets read biosalo.fi's API, location 2. Address from the cinema's page (Pussitie 4, Paimio); OSM has the cinema node.",
    venues: [
      {
        slug: "paimio",
        locationId: "2",
        page: "/",
        name: "Bio Stara",
        city: "Paimio",
        address: "Pussitie 4",
        postalCode: "21530",
        geo: { lat: 60.4571056, lon: 22.6895365 },
        geoSource: "osm:node/11168933714",
      },
    ],
  },
  {
    provider: "biojukola",
    name: "Bio Jukola",
    homepage: "https://biojukola.fi",
    apiBase: "https://biosalo.fi",
    programmePath: "/",
    titlePrefixes: { Ennakkonäytökset: { tags: ["preview"] } },
    verifiedAt: "2026-10-16",
    notes:
      "Bio-Salo's third cinema: biojukola.fi's widgets read biosalo.fi's API, location 4 (Kinoset's location 4 is empty). Address from nytleffaan.fi's directory (Jukolantie 4, Somero); OSM has the cinema node.",
    venues: [
      {
        slug: "somero",
        locationId: "4",
        page: "/",
        name: "Bio Jukola",
        city: "Somero",
        address: "Jukolantie 4",
        postalCode: "31400",
        geo: { lat: 60.6311472, lon: 23.5147802 },
        geoSource: "osm:node/13697462655",
      },
    ],
  },
  {
    provider: "kinokellokas",
    name: "Kino Kellokas",
    homepage: "https://kinokellokas.fi",
    programmePath: "/naytoslista/",
    verifiedAt: "2026-10-30",
    notes:
      "Kolari's cinema, in Äkäslompolo; found through elokuviin.com (2026-10-30). Location 1 has the shows; 2 and 3 are empty. Address from its own page.",
    venues: [
      {
        slug: "akaslompolo",
        locationId: "1",
        name: "Kino Kellokas",
        city: "Kolari",
        address: "Tunturintie 54",
        postalCode: "95970",
        geo: { lat: 67.589719, lon: 24.204695 },
        geoSource: "osm:node/6428212330",
      },
    ],
  },
]);
