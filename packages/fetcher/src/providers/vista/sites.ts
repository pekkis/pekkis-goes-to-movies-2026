import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Cinemas whose Vista public web services are open (no token): one GET per area returns
 * every show in the window, each with its theatre id. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/vista.py, AGPL-3.0); re-verified 2026-10-13.
 */
export const VistaVenue = SiteVenue.extend({
  /** The schedule's `TheatreID` for this venue. */
  theatreId: z.number().int(),
});

export const VistaSite = SiteBase.extend({
  /** The site root; the API is `{base}/xml/…`. */
  base: z.url(),
  /** `TheatreAreas` ids to read (one request each); absent: one request for every theatre. */
  areas: z.array(z.number().int()).min(1).optional(),
  /** What `/xml/Schedule/` answers: JSON (Korjaamo) unless the site serves only XML (Riviera). */
  format: z.enum(["json", "xml"]).optional(),
  venues: z.array(VistaVenue).min(1),
  /**
   * `ProductionYear` is the (re-)release year, not the film's: "Scream (1996)" says 2026.
   * Then only a year in the title is used.
   */
  releaseYearAsProductionYear: z.boolean().optional(),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type VistaSite = z.infer<typeof VistaSite>;

export const VISTA_SITES: VistaSite[] = defineSites(VistaSite, [
  {
    provider: "korjaamo",
    name: "Korjaamo Kino",
    homepage: "https://korjaamokino.fi",
    base: "https://korjaamokino.fi",
    areas: [1007],
    verifiedAt: "2026-10-13",
    titlePrefixes: {
      Kirjastokino: { series: "Kirjastokino" },
      Tekijätorstai: { series: "Tekijätorstai" },
    },
    notes: "OSM node has no address; the cinema's own page gives Töölönkatu 51 B (2026-10-13).",
    venues: [
      {
        slug: "helsinki",
        name: "Korjaamo Kino",
        city: "Helsinki",
        address: "Töölönkatu 51 B",
        postalCode: "00250",
        geo: { lat: 60.184283, lon: 24.920043 },
        geoSource: "osm:node/4394184115",
        theatreId: 1045,
      },
    ],
  },
  {
    provider: "riviera",
    name: "Riviera",
    homepage: "https://www.rivieracinemas.fi",
    base: "https://tickets.rivieracinemas.fi",
    format: "xml",
    releaseYearAsProductionYear: true,
    verifiedAt: "2026-10-14",
    titlePrefixes: {
      "3 Kaveria jäätelönäytös": { series: "3 Kaveria jäätelönäytös" },
      "Afternoon Tea": { series: "Afternoon Tea" },
      Leffabrunssi: { series: "Leffabrunssi" },
      Mykkäleffakonsertti: { series: "Mykkäleffakonsertti" },
    },
    notes:
      "The ticket host's open schedule (XML only; `area` not needed). The website's own listing is a WordPress admin-ajax POST, which we do not use. Addresses from the cinema's site, 2026-10-14.",
    venues: [
      {
        slug: "kallio",
        name: "Riviera Kallio",
        city: "Helsinki",
        address: "Harjukatu 2",
        postalCode: "00500",
        geo: { lat: 60.1877458, lon: 24.957698 },
        geoSource: "osm:node/5175303248",
        theatreId: 1075,
      },
      {
        slug: "punavuori",
        name: "Riviera Punavuori",
        city: "Helsinki",
        address: "Telakkakatu 7",
        postalCode: "00150",
        geo: { lat: 60.1588358, lon: 24.9331173 },
        geoSource: "osm:node/10186691049",
        theatreId: 1114,
      },
    ],
  },
  {
    provider: "biokaari",
    name: "Bio-Kaari",
    homepage: "https://www.bio-kaari.fi",
    base: "https://bio-kaari.azurewebsites.net",
    format: "xml",
    verifiedAt: "2026-10-15",
    notes:
      "The ticket host's open schedule (XML). Leffavuoro reads its MyCloudCinema web shop pages instead. The cinema's own site did not answer on 2026-10-15; OSM gives the street without a number.",
    venues: [
      {
        slug: "forssa",
        name: "Bio-Kaari",
        city: "Forssa",
        postalCode: "30300",
        geo: { lat: 60.816086, lon: 23.6279503 },
        geoSource: "osm:node/1142403445",
        theatreId: 1048,
      },
    ],
  },
]);
