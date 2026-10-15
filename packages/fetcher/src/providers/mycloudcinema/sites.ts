import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { SiteBase } from "../sites.ts";

/**
 * MyCloudCinema: a ticketing platform whose `/webservices` JSON API (plain GETs, no key) a
 * cinema's own webshop reads. One adapter per site; venues, halls and coordinates come from
 * the API itself (fix them in config/venue-overrides.json), not from this config.
 * Cine Mäntsälä's specifics were mapped by Leffavuoro (Shady-Dev/kino,
 * scripts/providers/cinemantsala.py, AGPL-3.0) and re-verified here.
 */
export const MyCloudCinemaSite = SiteBase.extend({
  /** The webservices root, e.g. https://webshop.biorex.fi/webservices. */
  api: z.url(),
  /**
   * Ticket links are `{ticketBase}/#/book/{show_time_id}`, the pattern the cinema's own
   * programme page links to (copied, never requested).
   */
  ticketBase: z.url(),
  /** Read only these cinema ids (default: every active cinema the API lists). */
  cinemaIds: z.array(z.number().int().positive()).optional(),
  /** Cities for cinemas whose API record leaves `city` empty, by cinema id. */
  cityOverrides: z.record(z.string(), z.string()).default({}),
  /** Whole `title_extension` labels of this site, besides the shared ones, any case. */
  titleExtensions: z.record(z.string(), LabelRule).default({}),
});
export type MyCloudCinemaSite = z.infer<typeof MyCloudCinemaSite>;

const sites = z.array(MyCloudCinemaSite).parse([
  {
    provider: "biorex",
    name: "BioRex",
    homepage: "https://biorex.fi",
    api: "https://webshop.biorex.fi/webservices",
    ticketBase: "https://webshop.biorex.fi/fi",
    // The API leaves `city` empty for these (verified 2026-10-09).
    cityOverrides: { "13": "Helsinki", "14": "Helsinki" }, // Tripla, Redi
    verifiedAt: "2026-10-09",
    notes: "Same pattern biorex.fi links to (data-click-data-layer).",
  },
  {
    provider: "cinemantsala",
    name: "Cine Mäntsälä",
    homepage: "https://mantsala.cine.fi",
    api: "https://mantsala.cine.fi/webservices",
    ticketBase: "https://mantsala.cine.fi",
    cinemaIds: [1],
    // The cinema's matinée strand (seen 2026-10-15).
    titleExtensions: { "Cine Matinea - näytös": { series: "Cine Matinea" } },
    verifiedAt: "2026-10-13",
    notes:
      "The API also lists cinema 2, Cine Keuda-talo (Kerava), which we read from eTiketti " +
      "(kiertue.cine.fi); it had no shows on either on 2026-10-13. No coordinates in the API: " +
      "see config/venue-overrides.json.",
  },
]);

const providers = sites.map((s) => s.provider);
if (new Set(providers).size !== providers.length) {
  throw new Error(`Duplicate MyCloudCinema provider in ${providers.join(", ")}`);
}

export const MYCLOUDCINEMA_SITES: readonly MyCloudCinemaSite[] = sites;
