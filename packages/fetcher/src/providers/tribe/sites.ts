import { z } from "zod";
import { Provider } from "@pgtm/model";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Cinemas whose programme is a category of The Events Calendar (WordPress): one REST
 * request per 50 events. Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/tribe.py,
 * AGPL-3.0); re-verified 2026-10-14.
 */
export const TribeSite = SiteBase.extend({
  /** The WordPress root. */
  base: z.url(),
  /** The film category's numeric id (stable, unlike its name): the rest is concerts. */
  category: z.number().int(),
  venues: z.array(SiteVenue).length(1),
  booking: Provider.shape.booking,
  /** Endings that are not part of the title: "Lapin sota -elokuvanäytös". */
  titleSuffixes: z.array(z.string().min(1)),
  /**
   * Titles written "English [Finnish]": "Tell Everyone [Kerro kaikille]" (Ritz, 2026-10-20).
   * The bracketed part is the Finnish title, the rest the English one.
   */
  bracketedFinnishTitle: z.boolean().optional(),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type TribeSite = z.infer<typeof TribeSite>;

export const TRIBE_SITES: TribeSite[] = defineSites(TribeSite, [
  {
    provider: "ritzvaasa",
    name: "Ritz Vaasa",
    homepage: "https://ritz.fi",
    base: "https://ritz.fi",
    category: 19,
    booking: "door",
    titleSuffixes: [],
    bracketedFinnishTitle: true,
    // Events whose films are announced later (2026-10-30).
    titlePrefixes: {
      "Knitting Cinema": { series: "Neulekino", event: true },
      "Ritz Horrorfest": { series: "Ritz Horrorfest", event: true },
    },
    verifiedAt: "2026-10-14",
    notes: 'Tickets at the door ("sold at the door" in every description).',
    venues: [
      {
        slug: "vaasa",
        name: "Ritz",
        city: "Vaasa",
        address: "Kirkkopuistikko 22a",
        postalCode: "65100",
        geo: { lat: 63.0957908, lon: 21.6087345 },
        geoSource: "osm:node/3060592153",
      },
    ],
  },
  {
    provider: "tahtikino",
    name: "Tähti Kino",
    homepage: "https://muhos.fi",
    base: "https://muhos.fi",
    category: 106,
    booking: "door",
    titleSuffixes: ["-elokuvanäytös"],
    verifiedAt: "2026-10-14",
    notes:
      "The municipality's calendar. Address from the events' venue (Muhostie 2), where OSM has the cinema node. Tickets at the door (\"ovelta\").",
    venues: [
      {
        slug: "muhos",
        name: "Tähti Kino",
        city: "Muhos",
        address: "Muhostie 2",
        postalCode: "91500",
        geo: { lat: 64.8097131, lon: 25.9874751 },
        geoSource: "osm:node/4946909729",
      },
    ],
  },
]);
