import ky, { HTTPError, type KyInstance } from "ky";
import PQueue from "p-queue";

/** `contact` (URL or email) lets cinemas reach whoever runs the fetcher. */
export const userAgent = (contact?: string): string =>
  `pekkis-goes-to-movies/0.1 (open source showtime aggregator${contact ? `; ${contact}` : ""})`;

export type HttpClient = {
  getJson: (url: string, searchParams?: Record<string, string | number>) => Promise<unknown>;
  /** For server-rendered pages (eTiketti). */
  getText: (url: string) => Promise<string>;
  /**
   * A read-only form POST, for the few sources that publish their programme no other way
   * (Kino Regina): the same request the cinema's own listing makes. Never for booking.
   */
  postForm: (url: string, form: Record<string, string>) => Promise<string>;
};

export type HttpClientOptions = {
  /** Max requests per `intervalMs` per host. */
  intervalCap?: number;
  intervalMs?: number;
  /** Parallel requests per host. */
  concurrency?: number;
  timeoutMs?: number;
  /** Extra headers, e.g. authorization. */
  headers?: Record<string, string>;
  /** Goes into the User-Agent. */
  contact?: string;
  /** Tests pass a fake; requests otherwise go through the global fetch. */
  fetch?: typeof fetch;
};

/**
 * The longest `Retry-After` we wait for. A server busy for a moment gets its pause; one
 * under maintenance ("Retry-After: 7200", Bio-Salo and Kuusamotalo on 2026-10-21) is not
 * retried at all, so one source can't stall a whole pull for hours.
 */
export const MAX_RETRY_AFTER_MS = 30_000;

/** A `Retry-After` value (seconds or an HTTP date) in milliseconds from `now`; undefined if absent or unreadable. */
export const retryAfterMs = (value: string | null, now: Date = new Date()): number | undefined => {
  if (value === null || value.trim() === "") {
    return undefined;
  }
  if (/^\d+$/.test(value.trim())) {
    return Number(value.trim()) * 1000;
  }
  const date = Date.parse(value);
  return Number.isNaN(date) ? undefined : Math.max(0, date - now.getTime());
};

/**
 * Polite HTTP client: identifiable User-Agent, retries, and per-host pacing so that
 * one source is never hit with parallel bursts.
 */
/**
 * Decodes a body by the charset its Content-Type states ("text/html;charset=ISO-8859-1",
 * Kino-Kuva); UTF-8 when none is stated or the label is unknown. Response.text() would
 * always assume UTF-8.
 */
export const decodeBody = (body: ArrayBuffer, contentType: string | null): string => {
  const label = contentType?.match(/charset\s*=\s*"?([^";\s]+)/i)?.[1] ?? "utf-8";
  try {
    return new TextDecoder(label).decode(body);
  } catch {
    return new TextDecoder("utf-8").decode(body);
  }
};

export const createHttpClient = ({
  intervalCap = 1,
  intervalMs = 750,
  concurrency = 1,
  timeoutMs = 20_000,
  headers = {},
  contact,
  fetch: fetchImpl,
}: HttpClientOptions = {}): HttpClient => {
  const client: KyInstance = ky.create({
    timeout: timeoutMs,
    retry: {
      limit: 2,
      maxRetryAfter: MAX_RETRY_AFTER_MS,
      // A long wait asked for means maintenance: fail now, the next pull will try again.
      shouldRetry: ({ error }) => {
        const wait =
          error instanceof HTTPError
            ? retryAfterMs(error.response.headers.get("Retry-After"))
            : undefined;
        return wait !== undefined && wait > MAX_RETRY_AFTER_MS ? false : undefined;
      },
    },
    ...(fetchImpl && { fetch: fetchImpl }),
    headers: { "user-agent": userAgent(contact), accept: "application/json", ...headers },
  });

  const queues = new Map<string, PQueue>();
  const queueFor = (host: string): PQueue => {
    let queue = queues.get(host);
    if (!queue) {
      queue = new PQueue({ concurrency, intervalCap, interval: intervalMs });
      queues.set(host, queue);
    }
    return queue;
  };

  return {
    getJson: (url, searchParams) =>
      queueFor(new URL(url).host).add(() => client.get(url, { searchParams }).json<unknown>()),
    getText: (url) =>
      queueFor(new URL(url).host).add(async () => {
        const response = await client.get(url, {
          headers: { accept: "text/html,application/xhtml+xml" },
        });
        return decodeBody(await response.arrayBuffer(), response.headers.get("content-type"));
      }),
    postForm: (url, form) =>
      queueFor(new URL(url).host).add(() =>
        client
          .post(url, { body: new URLSearchParams(form), headers: { accept: "text/html" } })
          .text(),
      ),
  };
};
