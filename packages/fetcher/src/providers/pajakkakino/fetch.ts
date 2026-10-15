import type { HttpClient } from "../../lib/http.ts";
import type { PajakkakinoSite } from "./sites.ts";

export type PajakkakinoRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** `/wp-json/wp/v2/posts`: every post, one per film. */
  posts: unknown;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the posts (a handful; the cinema keeps one per film). */
export const fetchPajakkakino = async (
  http: HttpClient,
  site: PajakkakinoSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<PajakkakinoRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const posts = await http.getJson(`${site.base}/wp-json/wp/v2/posts`, {
    per_page: 40,
    _fields: "id,link,title,content",
  });
  return { fetchedAt, from, days, posts };
};
