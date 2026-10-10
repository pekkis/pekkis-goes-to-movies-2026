import type { Kysely } from "kysely";
import type { DB } from "../db/types.ts";

/** Optional narrowing of a film's screenings (the `showtimes` CLI's --provider and --near). */
export type ScreeningFilter = {
  /** Provider ids (as stored), already resolved from names; see resolveProviders. */
  providerIds?: string[];
  near?: { lat: number; lon: number; radiusKm: number };
  /** "HH:MM" Helsinki time on the date; later shows (also after midnight) are kept. */
  after?: string;
  /**
   * "HH:MM": only shows starting before this. Earlier than (or equal to) `after` means the
   * next morning, so `after 22:00, before 02:00` is one late-night window.
   */
  before?: string;
};

/** "2026-10-10" -> "2026-10-11". */
export const nextDay = (date: string): string => {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
};

/** "18:00" or "9:30" -> "18:00" / "09:30"; undefined when not a time of day. */
export const parseTime = (raw: string): string | undefined => {
  const m = raw.trim().match(/^([01]?\d|2[0-3])[:.]([0-5]\d)$/);
  return m ? `${m[1]!.padStart(2, "0")}:${m[2]}` : undefined;
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
