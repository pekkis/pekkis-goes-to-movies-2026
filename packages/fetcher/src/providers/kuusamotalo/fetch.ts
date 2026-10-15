import type { HttpClient } from "../../lib/http.ts";
import type { KuusamotaloSite } from "./sites.ts";

export type KuusamotaloRawSnapshot = {
  fetchedAt: string;
  from: string;
  days: number;
  /** `/wp-json/wp/v2/posts`: every post, films and notices. */
  posts: unknown;
};

export type FetchOptions = { from: string; days: number; now?: () => Date };

/** I/O only: one GET of the posts (a handful; the cinema keeps one per film). */
export const fetchKuusamotalo = async (
  http: HttpClient,
  site: KuusamotaloSite,
  { from, days, now = () => new Date() }: FetchOptions,
): Promise<KuusamotaloRawSnapshot> => {
  const fetchedAt = now().toISOString();
  const posts = await http.getJson(`${site.base}/wp-json/wp/v2/posts`, {
    per_page: 40,
    _fields: "id,link,title,content",
  });
  return { fetchedAt, from, days, posts };
};
