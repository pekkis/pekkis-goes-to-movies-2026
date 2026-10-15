import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Kirkkonummi's one-page Elementor site: each film is a heading followed by an icon
 * list of rows ("16.10. Perjantai klo18.00", two joined by " / "), every block published
 * twice (desktop and mobile). Reservations by phone. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/kirkkonummi.py, AGPL-3.0); re-verified 2026-10-15.
 */
export const KirkkonummiSite = SiteBase.extend({
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type KirkkonummiSite = z.infer<typeof KirkkonummiSite>;

export const KIRKKONUMMI_SITES: KirkkonummiSite[] = defineSites(KirkkonummiSite, [
  {
    provider: "kinokirkkonummi",
    name: "Kino Kirkkonummi",
    homepage: "https://kinokirkkonummi.fi",
    verifiedAt: "2026-10-15",
    notes: "Address from the cinema's page (Munkinmäentie 17), 2026-10-15.",
    venues: [
      {
        slug: "kirkkonummi",
        name: "Kino Kirkkonummi",
        city: "Kirkkonummi",
        address: "Munkinmäentie 17",
        postalCode: "02400",
        geo: { lat: 60.1185412, lon: 24.4392085 },
        geoSource: "osm:way/136880152",
      },
    ],
  },
]);
