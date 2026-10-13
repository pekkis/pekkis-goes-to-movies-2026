import { dayScreenings, listVenues, type Api, type Screening, type Venue } from "./api.ts";
import { resolveCity, type City } from "./cities.ts";
import { isIsoDate } from "./time.ts";
import { resolveVenue } from "./venues.ts";

/** A valid `?date=`, or undefined: a malformed one falls back to the API's today. */
const dateOf = (param: string | null) => (param && isIsoDate(param) ? param : undefined);

export type CityPage = { city: City; venues: Venue[]; date: string; screenings: Screening[] };

/** Data for /fi/kaupungit/{slug}, or undefined for an unknown city. */
export const loadCityPage = async (
  api: Api,
  slug: string,
  dateParam: string | null,
): Promise<CityPage | undefined> => {
  const all = await listVenues(api);
  const city = resolveCity(slug, all);
  if (!city) return undefined;
  const { date, items } = await dayScreenings(api, { city: city.name }, dateOf(dateParam));
  return { city, venues: all.filter((v) => v.city === city.name), date, screenings: items };
};

export type VenuePage = { venue: Venue; date: string; screenings: Screening[] };

/** Data for /fi/elokuvateatterit/{slug}, or undefined for an unknown venue. */
export const loadVenuePage = async (
  api: Api,
  slug: string,
  dateParam: string | null,
): Promise<VenuePage | undefined> => {
  const venue = resolveVenue(slug, await listVenues(api));
  if (!venue) return undefined;
  const { date, items } = await dayScreenings(api, { venue: venue.id }, dateOf(dateParam));
  return { venue, date, screenings: items };
};
