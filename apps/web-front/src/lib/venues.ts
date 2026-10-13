import { citySlug } from "./cities.ts";

type Named = { name: string; city: string };

/**
 * URL slug for a venue: its name, plus the city unless the name already says it.
 * "Plevna Tampere" -> "plevna-tampere", "Kino Myyri" (Vantaa) -> "kino-myyri-vantaa".
 * Unique across every venue on 2026-10-13 (names alone are not: "Studio 123", "Maxim").
 * Derived from the current name: if a cinema is renamed, add a redirect for the old slug.
 */
export const venueSlug = ({ name, city }: Named): string => {
  const slug = citySlug(name);
  const place = citySlug(city);
  return new RegExp(`(^|-)${place}($|-)`).test(slug) ? slug : `${slug}-${place}`;
};

export const venuePath = (venue: Named): string => `/fi/elokuvateatterit/${venueSlug(venue)}`;

/** The venue a slug names, or undefined. */
export const resolveVenue = <V extends Named>(slug: string, venues: readonly V[]): V | undefined =>
  venues.find((v) => venueSlug(v) === slug);

/** OpenStreetMap at the venue's point, for "show on map". */
export const osmUrl = ({ lat, lon }: { lat: number; lon: number }): string =>
  `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=17/${lat}/${lon}`;
