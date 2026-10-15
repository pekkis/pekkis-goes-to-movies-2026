import { z } from "zod";
import { LabelRule } from "../labels.ts";
import { defineSites, SiteBase, SiteVenue } from "../sites.ts";

/**
 * Cinemas in the City of Helsinki's culture houses, read from the city's open Linked Events
 * API (CC BY 4.0). A house's calendar holds concerts and courses too, so a site lists the
 * title labels that make an event one of its screenings. Leffavuoro (Shady-Dev/kino,
 * scripts/providers/helios.py, AGPL-3.0) reads Malmitalo's own calendar by POST instead.
 */
export const LinkedEventsVenue = SiteVenue.extend({
  /** The Linked Events place id, e.g. "tprek:8740". */
  place: z.string().regex(/^[a-z]+:\d+$/),
});

export const LinkedEventsSite = SiteBase.extend({
  venues: z.array(LinkedEventsVenue).min(1),
  /**
   * "Label" as "Label: Title" or "Title – Label": only events carrying one of these are
   * screenings. `{}` marks the cinema's own name ("Tony (16) – Kino Helios").
   */
  labels: z.record(z.string(), LabelRule),
});
export type LinkedEventsSite = z.infer<typeof LinkedEventsSite>;

export const LINKED_EVENTS_SITES: LinkedEventsSite[] = defineSites(LinkedEventsSite, [
  {
    provider: "kinohelios",
    name: "Kino Helios",
    homepage: "https://www.malmitalo.fi",
    verifiedAt: "2026-10-15",
    labels: {
      "Kino Helios": {},
      HopeaCine: { series: "HopeaCine", tags: ["senior"] },
      "Yleisön suosikit": { series: "Yleisön suosikit" },
    },
    notes:
      "Malmitalo's cinema. Doc Helios and courses (Nuorten elokuvakerho) are other strands of the house and are not read.",
    venues: [
      {
        slug: "malmi",
        name: "Kino Helios",
        city: "Helsinki",
        address: "Ala-Malmin tori 1",
        postalCode: "00700",
        geo: { lat: 60.2505382, lon: 25.014476 },
        geoSource: "osm:way/29553571",
        place: "tprek:8740",
      },
    ],
  },
]);
