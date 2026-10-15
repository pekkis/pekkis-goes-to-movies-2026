import { Lang } from "@pgtm/model";
import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Kino Hamina, on the town's own site: one `large-content-showcase` block per film, a
 * paragraph of labelled fields (Ikäraja, Kesto, Liput, Versio) and a paragraph of
 * screenings ("To 22.10. Klo 15:00 (Liput 8€)"). Tickets at the door, no reservations.
 * Mapped by Leffavuoro (Shady-Dev/kino, scripts/providers/hamina.py, AGPL-3.0);
 * re-verified 2026-10-15.
 */
export const HaminaSite = SiteBase.extend({
  /** The cinema's page on the town's site. */
  programme: z.url(),
  venues: z.array(SiteVenue).length(1),
  /** "Versio:" values as the page's own legend defines them. */
  versions: z.record(
    z.string(),
    z.object({
      audio: Lang.optional(),
      dubbed: z.boolean().optional(),
      subtitles: z.array(Lang).optional(),
    }),
  ),
  /** Site-specific "Prefix: Title" rules, merged over COMMON_TITLE_PREFIXES. */
  titlePrefixes: z.record(z.string(), LabelRule).optional(),
});
export type HaminaSite = z.infer<typeof HaminaSite>;

export const HAMINA_SITES: HaminaSite[] = defineSites(HaminaSite, [
  {
    provider: "kinohamina",
    name: "Kino Hamina",
    homepage: "https://www.hamina.fi/hyvinvointi-vapaa-aika/kino-hamina/",
    programme: "https://www.hamina.fi/hyvinvointi-vapaa-aika/kino-hamina/",
    verifiedAt: "2026-10-15",
    // "OG = Alkuperäinen kieli, tekstitys suomeksi (ja) ruotsiksi. DUB = Puhuttu suomeksi."
    // Swedish is hedged in that sentence, so only Finnish subtitles are published.
    versions: {
      OG: { dubbed: false, subtitles: ["fi"] },
      DUB: { dubbed: true, audio: "fi" },
    },
    notes:
      "The page moved under /hyvinvointi-vapaa-aika/ (old path redirects). Address from the page (Isoympyräkatu 30 A); OSM has no cinema there, so the point is geocoded.",
    venues: [
      {
        slug: "hamina",
        name: "Kino Hamina",
        city: "Hamina",
        address: "Isoympyräkatu 30 A",
        postalCode: "49400",
        geo: { lat: 60.5702511, lon: 27.1934968 },
        geoSource: "nominatim",
      },
    ],
  },
]);
