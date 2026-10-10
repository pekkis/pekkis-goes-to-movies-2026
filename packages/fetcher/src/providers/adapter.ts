import type { Platform, ProviderBatch } from "@pgtm/model";
import type { Env } from "../lib/env.ts";

export type PullContext = { env: Env; out: string };

export type PullOptions = {
  from: string;
  days: number;
  /** Source venue ids or slugs to limit to (default: all). */
  venues?: string[];
};

/**
 * One provider (one output file, one `data/normalized/{id}.json`). Platform adapters such
 * as Nexxo produce one Adapter per configured site; see src/providers/sites.ts.
 */
export type Adapter = {
  id: string;
  /** Ticketing platform, so `pnpm pull --provider nexxo` selects every site on it. */
  platform: Platform;
  /** Fetches (I/O) and parses (pure); returns the raw snapshot for archiving too. */
  pull: (
    ctx: PullContext,
    options: PullOptions,
  ) => Promise<{ raw: { fetchedAt: string }; batch: ProviderBatch }>;
};

/**
 * Keeps only the given venues (matched by source id or id slug) and what they reference.
 * Ingest marks removals per venue in the batch, so a partial pull must not list venues it
 * did not fetch.
 */
export const restrictToVenues = (
  batch: ProviderBatch,
  keys: string[] | undefined,
): ProviderBatch => {
  if (!keys) return batch;
  const venues = batch.venues.filter(
    (v) => keys.includes(v.sourceId) || keys.includes(v.id.split(":").at(-1)!),
  );
  const venueIds = new Set(venues.map((v) => v.id));
  const screenings = batch.screenings.filter((s) => venueIds.has(s.venueId));
  const listingIds = new Set(screenings.map((s) => s.listingId));
  return {
    ...batch,
    venues,
    auditoriums: batch.auditoriums.filter((a) => venueIds.has(a.venueId)),
    listings: batch.listings.filter((l) => listingIds.has(l.id)),
    screenings,
  };
};
