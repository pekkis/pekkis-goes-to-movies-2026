import { z } from "zod";
import { ScreeningTag } from "@pgtm/model";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Elokuvateatteri Iso-Hannu's own PHP site: the front page's `#showtable` lists a week,
 * a day heading with its year, one table per hall, one row per screening with the film's
 * id and the screening's own ticket link. Each film's page adds runtime, age limit, genre
 * and spoken language. Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/isohannu.py,
 * AGPL-3.0); re-verified 2026-10-14.
 */
export const IsohannuSite = SiteBase.extend({
  /** The site root, whose front page carries the programme. */
  base: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** `showtable-{name}` tag classes and the screening tags they mean; `[]` means ignore. */
  tags: z.record(z.string(), z.array(ScreeningTag)),
  /** Row titles that are not screenings (a private booking of a hall), any case. */
  notScreenings: z.array(z.string().min(1)),
});
export type IsohannuSite = z.infer<typeof IsohannuSite>;

export const ISOHANNU_SITES: IsohannuSite[] = defineSites(IsohannuSite, [
  {
    provider: "isohannu",
    name: "Elokuvateatteri Iso-Hannu",
    homepage: "https://www.isohannu.fi",
    base: "https://www.isohannu.fi",
    verifiedAt: "2026-10-14",
    tags: {
      tickets: [],
      children: ["kids"],
      premiere: ["premiere"],
      finalshow: ["last-screening"],
    },
    notScreenings: ["Salissa yksityisvaraus"],
    notes: "Address from the cinema's own page (Savilankatu 4, 26100 Rauma), 2026-10-14.",
    venues: [
      {
        slug: "rauma",
        name: "Iso-Hannu",
        city: "Rauma",
        address: "Savilankatu 4",
        postalCode: "26100",
        geo: { lat: 61.1284914, lon: 21.5080357 },
        geoSource: "osm:way/128190368",
      },
    ],
  },
]);
