/**
 * Headers for every page. Until every cinema has been notified (AGENTS.md), search engines
 * are told to stay out: `INDEXING=on` is for the production deployment only.
 */
export const pageHeaders = (headers: Headers, { indexing }: { indexing: boolean }): void => {
  if (!indexing) headers.set("X-Robots-Tag", "noindex, nofollow");
  // The programme changes about daily; a minute of caching keeps load low without staleness.
  if (headers.get("content-type")?.startsWith("text/html") && !headers.has("cache-control")) {
    headers.set("Cache-Control", "public, max-age=60");
  }
};
