import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Cinema Levi Summit (Kittilä): the cinema page's show calendar has one section per day
 * ("Torstai 15.10.2026"), and in it one card per screening with the `h4` title, the time
 * ("To klo 14:00") and the adult price. Read 2026-10-15; the site was found by the
 * maintainer.
 */
export const LeviSummitSite = SiteBase.extend({
  /** The cinema page with the show calendar. */
  programme: z.url(),
  /** Film pages live here (the operator's WordPress); others are not linked. */
  filmPagePrefix: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type LeviSummitSite = z.infer<typeof LeviSummitSite>;

export const LEVISUMMIT_SITES: LeviSummitSite[] = defineSites(LeviSummitSite, [
  {
    provider: "levisummit",
    name: "Cinema Levi Summit",
    homepage: "https://levisummit.fi/cinema/",
    programme: "https://levisummit.fi/cinema/",
    filmPagePrefix: "https://www.kassiopeia.fi/levi-summit/",
    verifiedAt: "2026-10-15",
    notes:
      "The site states no street address; address and coordinates from OSM (Levi Summit, Levin portaat, 99130 Sirkka, Kittilä), 2026-10-15. The calendar shows the current week.",
    venues: [
      {
        slug: "levi",
        name: "Cinema Levi Summit",
        city: "Kittilä",
        address: "Levin portaat",
        postalCode: "99130",
        geo: { lat: 67.8002689, lon: 24.811167 },
        geoSource: "osm:node/1747051981",
      },
    ],
  },
]);
