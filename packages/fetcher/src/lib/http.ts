import ky, { type KyInstance } from "ky";
import PQueue from "p-queue";

/** `contact` (URL or email) lets cinemas reach whoever runs the fetcher. */
export const userAgent = (contact?: string): string =>
  `pekkis-goes-to-movies/0.1 (open source showtime aggregator${contact ? `; ${contact}` : ""})`;

export type HttpClient = {
  getJson: (url: string, searchParams?: Record<string, string | number>) => Promise<unknown>;
  /** For server-rendered pages (eTiketti). */
  getText: (url: string) => Promise<string>;
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
};

/**
 * Polite HTTP client: identifiable User-Agent, retries, and per-host pacing so that
 * one source is never hit with parallel bursts.
 */
export const createHttpClient = ({
  intervalCap = 1,
  intervalMs = 750,
  concurrency = 1,
  timeoutMs = 20_000,
  headers = {},
  contact,
}: HttpClientOptions = {}): HttpClient => {
  const client: KyInstance = ky.create({
    timeout: timeoutMs,
    retry: { limit: 2 },
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
      queueFor(new URL(url).host).add(() =>
        client.get(url, { headers: { accept: "text/html,application/xhtml+xml" } }).text(),
      ),
  };
};
