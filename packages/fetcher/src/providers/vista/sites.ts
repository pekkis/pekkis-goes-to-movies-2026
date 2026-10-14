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
  /** `TheatreAreas` ids to read (one request each). */
  areas: z.array(z.number().int()).min(1),
  venues: z.array(VistaVenue).min(1),
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
]);
