import type { HttpClient } from "../../lib/http.ts";
import type { GildaRawSnapshot } from "./raw.ts";
import type { GildaSite } from "./sites.ts";

export type FetchOptions = { from: string; days: number; now?: () => Date };

/**
 * I/O only, two GETs: every film with its showtimes (the facade the cinema's own programme
 * reads), and the public film pages that showtimes link to. The namespace also holds
 * write and administrative routes; they are never called.
 */
export const fetchGilda = async (
  http: HttpClient,
  site: GildaSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<GildaRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const movies = await http.getJson(`${site.base}/wp-json/gilda-react-booking/v1/movies`);
  const posts = await http.getJson(`${site.base}/wp-json/wp/v2/movies`, {
    per_page: 100,
    _fields: "link,title",
  });
  return { fetchedAt, from, days, movies, posts };
};
