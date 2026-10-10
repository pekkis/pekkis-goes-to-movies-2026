import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue, Slug } from "../sites.ts";

/**
 * Kinola (kinola.ee, an Estonian ticketing service) cinemas. Each has a tenant
 * `{tenant}.kinola.ee` whose public JSON API lists its events with the film embedded.
 * Adding a cinema = adding an entry here; the tenant is visible in the site's image URLs
 * (`media.kinola.ee/storage/{tenant}.kinola.ee/…`).
 *
 * Tenants from Leffavuoro (vendor/leffavuoro/scripts/providers/kinola.py), which reads the
 * sites' HTML; the API was found 2026-10-10 in Kinola's open-source WordPress plugin.
 */

export const KinolaVenue = SiteVenue.extend({
  /** The event's `venue.name` in the API ("Marsio" for Cinema Sheryl). */
  kinolaName: z.string().min(1),
});
export type KinolaVenue = z.infer<typeof KinolaVenue>;

export const KinolaSite = SiteBase.extend({
  tenant: Slug,
  venues: z.array(KinolaVenue).min(1),
  /** Where a screening without a checkout link sends people (the programme page). */
  programmePath: z.string().startsWith("/"),
  /**
   * Productions with no language, no distributor and no IMDb id are live acts (concerts,
   * stand-up), not films. True only where that was checked against the programme
   * (Kino Laika): elsewhere real films lack those too.
   */
  bareProductionsAreEvents: z.boolean().optional(),
  /** `program.name` rules: series, categories to ignore (`{}`), bar service. */
  programs: z.record(z.string(), LabelRule).optional(),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KinolaSite = z.infer<typeof KinolaSite>;

export const apiBase = (site: KinolaSite) => `https://${site.tenant}.kinola.ee/api/public/v1`;

const V = "2026-10-10";

export const KINOLA_SITES: KinolaSite[] = defineSites(KinolaSite, [
  {
    provider: "kinomyyri",
    name: "Kino Myyri",
    homepage: "https://www.myyrikino.fi",
    tenant: "myyri",
    programmePath: "/ohjelmisto/",
    verifiedAt: V,
    programs: { "Muut kuin kotimaiset kielet": {}, Dokumentit: {} },
    titlePrefixes: {
      Cinemaissi: { series: "Cinemaissi" },
      "Espanjalaisen elokuvan viikko": { series: "Espanjalaisen elokuvan viikko" },
    },
    venues: [
      {
        slug: "myyrmaki",
        name: "Kino Myyri",
        city: "Vantaa",
        kinolaName: "Kino Myyri",
        address: "Kinorinne 6",
        postalCode: "01600",
        geo: { lat: 60.26131, lon: 24.854139 },
        geoSource: "osm:node/573388225",
      },
    ],
  },
  {
    provider: "cinemaorion",
    name: "Cinema Orion",
    homepage: "https://cinemaorion.fi",
    tenant: "orion",
    programmePath: "/",
    verifiedAt: V,
    notes: "KAVI's cinema. Checkout links go to Kinola's own screening pages (orion.kinola.ee).",
    titlePrefixes: { Kinokonsertti: { series: "Kinokonsertti" } },
    venues: [
      {
        slug: "helsinki",
        name: "Cinema Orion",
        city: "Helsinki",
        kinolaName: "Cinema Orion",
        address: "Eerikinkatu 15",
        postalCode: "00100",
        geo: { lat: 60.166431, lon: 24.93276 },
        geoSource: "osm:node/5203779098",
      },
    ],
  },
  {
    provider: "kinokilta",
    name: "Kino Kilta",
    homepage: "https://www.kinokilta.fi",
    tenant: "kilta",
    programmePath: "/naytokset/",
    verifiedAt: V,
    notes:
      "Sells tickets outside Kinola: the API gives no checkout link, so shows link the programme.",
    programs: {
      "Anniskelunäytös K18": { licensed: true },
      "KUVIn aluesarja": { series: "KUVIn aluesarja" },
      Kahvikino: { series: "Kahvikino" },
    },
    titlePrefixes: { Kinokopla: { series: "Kinokopla" } },
    venues: [
      {
        slug: "turku",
        name: "Kino Kilta",
        city: "Turku",
        kinolaName: "Kino Kilta",
        address: "Nunnankatu 4",
        postalCode: "20700",
        geo: { lat: 60.450108, lon: 22.276268 },
        geoSource: "osm:node/12899811460",
      },
    ],
  },
  {
    provider: "kinolaika",
    name: "Kino Laika",
    homepage: "https://www.kinolaika.fi",
    tenant: "laika",
    programmePath: "/ohjelmisto/",
    verifiedAt: V,
    bareProductionsAreEvents: true,
    notes:
      "Hosts gigs as productions too. Checked 2026-10-10: its productions with no language, " +
      "distributor or IMDb id are live acts (Arppa, Antti Autio, Mariska, Knipi, …).",
    venues: [
      {
        slug: "karkkila",
        name: "Kino Laika",
        city: "Karkkila",
        kinolaName: "Kino Laika",
        address: "Valurinkatu 2c",
        postalCode: "03600",
        geo: { lat: 60.531223, lon: 24.203679 },
        geoSource: "osm:node/9806374143",
      },
    ],
  },
  {
    provider: "cinemasheryl",
    name: "Cinema Sheryl",
    homepage: "https://sheryl.fi",
    tenant: "sheryl",
    programmePath: "/",
    verifiedAt: V,
    notes: "Student cinema in Aalto's Marsio building, Otaniemi; the API says Helsinki.",
    venues: [
      {
        slug: "otaniemi",
        name: "Cinema Sheryl",
        city: "Espoo",
        kinolaName: "Marsio",
        address: "Otakaari 2",
        postalCode: "02150",
        geo: { lat: 60.1866, lon: 24.826482 },
        geoSource: "osm:node/13180200001",
      },
    ],
  },
  {
    provider: "kinokonepaja",
    name: "Kino Konepaja",
    homepage: "https://kinokonepaja.fi",
    tenant: "konepaja",
    programmePath: "/",
    verifiedAt: V,
    titlePrefixes: { Muutoskollektiivi: { series: "Muutoskollektiivi" } },
    venues: [
      {
        slug: "helsinki",
        name: "Kino Konepaja",
        city: "Helsinki",
        kinolaName: "Kino Konepaja",
        address: "Konepajanpasaasi",
        postalCode: "00510",
        geo: { lat: 60.193815, lon: 24.945327 },
        geoSource: "osm:node/12165817359",
      },
    ],
  },
]);
