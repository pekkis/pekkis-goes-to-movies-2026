import { ScreeningTag } from "@pgtm/model";
import { z } from "zod";
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
export const ShowTypeRule = z.object({
  tags: z.array(ScreeningTag).optional(),
  event: z.boolean().optional(),
});
export type ShowTypeRule = z.infer<typeof ShowTypeRule>;

/** Platform defaults; a site's `showTypes` overrides or extends them. */
export const DEFAULT_SHOW_TYPES: Record<string, ShowTypeRule> = {
  "Tavallinen näytös": {},
  "Viikko-ohjelmisto": {},
  Konsertti: { tags: ["event-cinema"], event: true },
  Taikashow: { tags: ["event-cinema"], event: true },
  "Muut tapahtumat": { tags: ["event-cinema"], event: true },
};

/**
 * A known "Prefix: Title" label. The prefix is stripped from the title (so TMDB matching
 * sees the film's own name) and becomes tags and/or a series. Only listed prefixes are
 * touched: "Ryhmä Hau: Dinoelokuva" is a title, not a label.
 */
export const TitlePrefixRule = z.object({
  tags: z.array(ScreeningTag).optional(),
  series: z.string().optional(),
});
export type TitlePrefixRule = z.infer<typeof TitlePrefixRule>;

export const DEFAULT_TITLE_PREFIXES: Record<string, TitlePrefixRule> = {
  "Ennakkoensi-ilta": { tags: ["preview"] },
  Ennakkonäytös: { tags: ["preview"] },
};

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
      Rauhanviikko: { series: "Rauhanviikko" },
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
        geo: { lat: 62.236619, lon: 25.735002 },
        geoSource: "nominatim",
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
  {
    provider: "kinomarilyn",
    name: "Kino Marilyn",
    homepage: "https://kinomarilyn.fi",
    programmePath: "/esitysajat/",
    verifiedAt: "2026-10-10",
    venues: [
      {
        slug: "loviisa",
        locationId: "1",
        name: "Kino Marilyn",
        city: "Loviisa",
        address: "Kuningattarenkatu 17",
        postalCode: "07900",
        geo: { lat: 60.458467, lon: 26.225406 },
        geoSource: "osm:node/2104773059",
      },
    ],
  },
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
      "were found by the unclaimed-room warning, not in Leffavuoro's list. Each town " +
      "plays in a hall (address from its town page, geocoded with Nominatim); Viitasaari " +
      "resolved only to the street, so its point is approximate.",
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
        geo: { lat: 63.084463, lon: 25.849328 },
        geoSource: "nominatim",
      },
    ],
  },
]);
