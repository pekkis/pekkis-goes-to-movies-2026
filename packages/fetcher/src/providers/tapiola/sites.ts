import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Tapiola's own WordPress theme: `/elokuvat/` renders one block per screening (title,
 * the date with its year, a link to the run's page), and each run's page carries the age
 * limit, runtime, spoken language and subtitles. Johku sells the tickets through widgets on
 * those pages; its API key is never used. Mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/tapiola.py, AGPL-3.0); re-verified 2026-10-14.
 */
export const TapiolaSite = SiteBase.extend({
  /** The site root; the programme is `{base}/elokuvat/`. */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
  /** `cat-{name}` classes on a row: the strand it belongs to. */
  categories: z.record(z.string(), LabelRule),
});
export type TapiolaSite = z.infer<typeof TapiolaSite>;

const EVENT_CINEMA = { tags: ["event-cinema" as const], event: true };

export const TAPIOLA_SITES: TapiolaSite[] = defineSites(TapiolaSite, [
  {
    provider: "kinotapiola",
    name: "Kino Tapiola",
    homepage: "https://www.kinotapiola.fi",
    base: "https://www.kinotapiola.fi",
    verifiedAt: "2026-10-14",
    titlePrefixes: {
      "The Royal Opera": { ...EVENT_CINEMA, series: "The Royal Opera" },
      "The Royal Ballet": { ...EVENT_CINEMA, series: "The Royal Ballet" },
    },
    categories: { seniorikino: { tags: ["senior"] } },
    notes: "Address from the cinema's own footer (Mäntyviita 2, 02110 Espoo), 2026-10-14.",
    venues: [
      {
        slug: "espoo",
        name: "Kino Tapiola",
        city: "Espoo",
        address: "Mäntyviita 2",
        postalCode: "02110",
        geo: { lat: 60.1788838, lon: 24.8110285 },
        geoSource: "osm:node/1430315541",
      },
    ],
  },
]);
