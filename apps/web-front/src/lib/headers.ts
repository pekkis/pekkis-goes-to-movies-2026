/**
 * The Content Security Policy we are heading for: our own scripts only, TMDB's images, and
 * OpenFreeMap's tiles for the map. It is sent report-only for now, so a browser's console
 * shows what it would block without breaking a page (Astro's inline island scripts would
 * need hashes: `security.csp` in astro.config). See docs/web.md#security-headers.
 */
export const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "worker-src 'self' blob:",
  // Vanilla Extract's dynamic values and MapLibre's markers set inline styles.
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://image.tmdb.org https://tiles.openfreemap.org",
  "connect-src 'self' https://tiles.openfreemap.org",
  "font-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

/**
 * Headers for every page. Until every cinema has been notified (AGENTS.md), search engines
 * are told to stay out: `INDEXING=on` is for the production deployment only.
 */
export const pageHeaders = (headers: Headers, { indexing }: { indexing: boolean }): void => {
  if (!indexing) {
    headers.set("X-Robots-Tag", "noindex, nofollow");
  }
  // The programme changes about daily; a minute of caching keeps load low without staleness.
  if (headers.get("content-type")?.startsWith("text/html") && !headers.has("cache-control")) {
    headers.set("Cache-Control", "public, max-age=60");
  }
  // If anything ever gets past escaping, these limit what it can do.
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  // Location only for our own "use my location" button; nothing else.
  headers.set("Permissions-Policy", "geolocation=(self), camera=(), microphone=(), payment=()");
  headers.set("Content-Security-Policy-Report-Only", CSP);
};
