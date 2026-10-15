import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Elokuvateatteri Julia 1&2's WordPress: `/ohjelmisto/` lists each film once in a
 * `div.elokuva` with its screenings ("15.10.26 klo 16:00, 1. sali") and labelled facts.
 * Tickets at the door. Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/julia.py,
 * AGPL-3.0); re-verified 2026-10-15.
 */
export const JuliaSite = SiteBase.extend({
  /** The programme page. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
  /** Genres that make a listing event cinema (opera, ballet, concert), any case. */
  eventGenres: z.array(z.string().min(1)),
});
export type JuliaSite = z.infer<typeof JuliaSite>;

export const JULIA_SITES: JuliaSite[] = defineSites(JuliaSite, [
  {
    provider: "julia",
    name: "Elokuvateatteri Julia",
    homepage: "https://juliaelokuvat.fi",
    programme: "https://juliaelokuvat.fi/ohjelmisto/",
    verifiedAt: "2026-10-15",
    eventGenres: ["Ooppera", "Baletti", "Konsertti"],
    notes: "Address from the cinema's own page (Hämeenkatu 34, 05800 Hyvinkää), 2026-10-15.",
    venues: [
      {
        slug: "hyvinkaa",
        name: "Julia 1&2",
        city: "Hyvinkää",
        address: "Hämeenkatu 34",
        postalCode: "05800",
        geo: { lat: 60.636281, lon: 24.8680871 },
        geoSource: "osm:node/2388923543",
      },
    ],
  },
]);
