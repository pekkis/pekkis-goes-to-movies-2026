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
  /** The Linked Events instance: Helsinki's by default, Espoo runs its own. */
  api: z.url(),
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
    api: "https://api.hel.fi/linkedevents/v1/event/",
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
  {
    provider: "kannusali",
    name: "Kannusali",
    homepage: "https://www.espoo.fi/fi/kulttuuri/kannusali",
    api: "https://api.espoo.fi/events/v1/event/",
    verifiedAt: "2026-10-15",
    labels: {
      Elokuva: {},
      "Lasten viikonloppu, Elokuva": { tags: ["kids"] },
      Elokuvakonsertti: { tags: ["event-cinema"], event: true },
    },
    notes:
      "Espoo's culture house in Espoon keskus, read from Espoo's own Linked Events instance (GET). Leffavuoro POSTs to espoo.fi/api/events instead.",
    venues: [
      {
        slug: "espoon-keskus",
        name: "Kannusali",
        city: "Espoo",
        address: "Kannusillankatu 4",
        postalCode: "02770",
        geo: { lat: 60.2060578, lon: 24.6531872 },
        geoSource: "osm:node/13744741583",
        place: "tprek:21430",
      },
    ],
  },
]);
