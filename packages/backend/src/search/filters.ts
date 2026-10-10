import type { Kysely } from "kysely";
import type { DB } from "../db/types.ts";

/** Optional narrowing of a film's screenings (the `showtimes` CLI's --provider and --near). */
export type ScreeningFilter = {
  /** Provider ids (as stored), already resolved from names; see resolveProviders. */
  providerIds?: string[];
  near?: { lat: number; lon: number; radiusKm: number };
};

/**
 * "62.24,25.75", "62.24, 25.75" or "@62.24,25.75" (a map link's form) -> point.
 * Undefined when malformed or outside the valid range.
 */
export const parseLatLon = (raw: string): { lat: number; lon: number } | undefined => {
  const m = raw
    .trim()
    .replace(/^@/, "")
    .match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)/);
  if (!m) return undefined;
  const lat = Number(m[1]);
  const lon = Number(m[2]);
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : undefined;
};

/**
 * Provider ids for names given as provider ids (`finnkino`, `kinoaurora`) or platforms
 * (`nexxo` = every Nexxo site), as `pnpm pull --provider` takes them.
 */
export const resolveProviders = async (
  db: Kysely<DB>,
  names: string[],
): Promise<{ ids: string[]; unknown: string[]; known: string[] }> => {
  const providers = await db.selectFrom("providers").select(["id", "platform"]).execute();
  const wanted = names.map((n) => n.toLowerCase());
  const ids = providers
    .filter((p) => wanted.includes(p.id) || wanted.includes(p.platform))
    .map((p) => p.id);
  const known = [...new Set(providers.flatMap((p) => [p.id, p.platform]))].sort();
  return { ids, unknown: wanted.filter((n) => !known.includes(n)), known };
};
