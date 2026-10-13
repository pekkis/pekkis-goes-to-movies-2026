import { cityScreenings, listVenues, type Api, type Screening } from "./api.ts";
import { resolveCity, type City } from "./cities.ts";
import { isIsoDate } from "./time.ts";

export type CityPage = { city: City; date: string; screenings: Screening[] };

/**
 * Data for /fi/kaupungit/{slug}: undefined for an unknown city. A malformed `?date=` is
 * ignored (the API's today is used) rather than failing the page.
 */
export const loadCityPage = async (
  api: Api,
  slug: string,
  dateParam: string | null,
): Promise<CityPage | undefined> => {
  const city = resolveCity(slug, await listVenues(api));
  if (!city) return undefined;
  const date = dateParam && isIsoDate(dateParam) ? dateParam : undefined;
  const { date: shown, items } = await cityScreenings(api, { city: city.name, date });
  return { city, date: shown, screenings: items };
};
