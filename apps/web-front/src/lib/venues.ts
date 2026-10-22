import { citySlug } from "./cities.ts";

type Named = { name: string; city: string };

/**
 * URL slug for a venue: its name, plus the city unless the name already says it.
 * "Plevna Tampere" -> "plevna-tampere", "Kino Myyri" (Vantaa) -> "kino-myyri-vantaa".
 * Unique across every venue on 2026-10-13 (names alone are not: "Studio 123", "Maxim").
 * Derived from the current name: if a cinema is renamed, add a redirect for the old slug.
 */
const namesCity = ({ name, city }: Named): boolean =>
  new RegExp(`(^|-)${citySlug(city)}($|-)`).test(citySlug(name));

export const venueSlug = (venue: Named): string =>
  namesCity(venue) ? citySlug(venue.name) : `${citySlug(venue.name)}-${citySlug(venue.city)}`;

/**
 * A venue as people should read it outside its own city's page: "Maxim, Varkaus", since
 * names repeat ("Maxim", "Studio 123"); "BioRex Tripla" or "Plevna Tampere" as they are
 * when the name already says the city.
 */
export const venueLabel = (venue: Named): string =>
  namesCity(venue) ? venue.name : `${venue.name}, ${venue.city}`;

export const venuePath = (venue: Named): string => `/fi/elokuvateatterit/${venueSlug(venue)}`;

/** The venue a slug names, or undefined. */
export const resolveVenue = <V extends Named>(slug: string, venues: readonly V[]): V | undefined =>
  venues.find((v) => venueSlug(v) === slug);

/** OpenStreetMap at the venue's point, for "show on map". */
export const osmUrl = ({ lat, lon }: { lat: number; lon: number }): string =>
  `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=17/${lat}/${lon}`;
