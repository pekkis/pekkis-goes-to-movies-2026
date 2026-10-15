import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Regina (KAVI, in Oodi): its theme's PHP endpoint answers a form POST with the whole
 * published programme as HTML, a row per screening with the film's id and a ticket link
 * into KAVI's shop. Each film's page adds runtime, countries, subtitles, themes, the print
 * and the age limit. This is our first POST source, allowed by the maintainer: it is the
 * request the cinema's own programme page makes, read-only. Mapped by Leffavuoro
 * (Shady-Dev/kino, scripts/providers/regina.py, AGPL-3.0); re-verified 2026-10-15.
 */
export const ReginaSite = SiteBase.extend({
  /** The endpoint that answers `getShowtimesMovies={date}` with the programme. */
  schedule: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type ReginaSite = z.infer<typeof ReginaSite>;

export const REGINA_SITES: ReginaSite[] = defineSites(ReginaSite, [
  {
    provider: "kinoregina",
    name: "Kino Regina",
    homepage: "https://kinoregina.fi",
    schedule:
      "https://kinoregina.fi/wp-content/themes/kinoregina2/assets/functions/getShowtimesMoviesV2.php",
    verifiedAt: "2026-10-15",
    notes:
      "The National Audiovisual Institute's cinema in the Central Library Oodi. Address from the cinema's info page and OSM, 2026-10-15.",
    venues: [
      {
        slug: "oodi",
        name: "Kino Regina",
        city: "Helsinki",
        address: "Töölönlahdenkatu 4",
        postalCode: "00100",
        geo: { lat: 60.1741861, lon: 24.9378675 },
        geoSource: "osm:node/9628528752",
      },
    ],
  },
]);
