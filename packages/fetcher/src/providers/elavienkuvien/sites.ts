import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Forssan Elävienkuvien teatteri (Foxy CMS): `/ohjelmisto/` lists the films, each film's
 * page has its runtime, age-limit image and screenings ("to 15.10.2026 klo 17:00", the
 * year printed) with the row's own reservation link. Mapped by Leffavuoro
 * (Shady-Dev/kino, scripts/providers/elavienkuvien.py, AGPL-3.0); re-verified 2026-10-15.
 */
export const ElavienkuvienSite = SiteBase.extend({
  /** The site root; links on its pages are relative to it (`<base href>`). */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type ElavienkuvienSite = z.infer<typeof ElavienkuvienSite>;

export const ELAVIENKUVIEN_SITES: ElavienkuvienSite[] = defineSites(ElavienkuvienSite, [
  {
    provider: "elavienkuvien",
    name: "Elävienkuvien teatteri",
    homepage: "https://www.elavienkuvienteatteri.fi",
    base: "https://www.elavienkuvienteatteri.fi/",
    verifiedAt: "2026-10-15",
    notes: "Address from the cinema's page and OSM (Keskuskatu 1, 30100 Forssa), 2026-10-15.",
    venues: [
      {
        slug: "forssa",
        name: "Elävienkuvien teatteri",
        city: "Forssa",
        address: "Keskuskatu 1",
        postalCode: "30100",
        geo: { lat: 60.8128682, lon: 23.62413 },
        geoSource: "osm:node/6733240707",
      },
    ],
  },
]);
