import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import type { FilmListing } from "@pgtm/model";
import { z } from "zod";
import { normalizeTitle, stripQualifiers } from "./titles.ts";

/**
 * Links made with certainty on an earlier run (search, IMDb id, sibling), by listing id.
 * A sibling match leans on another cinema's listing; when that cinema stops showing the
 * film (BioRex and Practical Magic, 2026-10-18), the memory keeps the others linked.
 * Aliases are not remembered: they are permanent already.
 */
export const RememberedLink = z.object({
  filmId: z.string().regex(/^tmdb:\d+$/),
  /** The listing's title key when linked: a renamed listing is not trusted. */
  titleKey: z.string().min(1),
  runtimeMinutes: z.number().int().positive().optional(),
  lastSeen: z.iso.datetime(),
});
export type RememberedLink = z.infer<typeof RememberedLink>;
export const Memory = z.record(z.string(), RememberedLink);
export type Memory = z.infer<typeof Memory>;

/** A link nobody has seen for this long is forgotten. */
const FORGET_AFTER_MS = 180 * 24 * 3_600_000;

/** Normalized title without qualifiers: the key siblings and memories are compared by. */
export const titleKey = (listing: FilmListing): string | undefined => {
  const title = listing.title.fi ?? listing.title.en ?? listing.title.sv;
  return title ? normalizeTitle(stripQualifiers(title)) : undefined;
};

/** Both runtimes known and within 3 minutes, or both unknown. */
export const sameRuntime = (a: number | undefined, b: number | undefined): boolean =>
  a === undefined || b === undefined ? a === b : Math.abs(a - b) <= 3;

/** The remembered film for a listing, if its title and runtime are still the same. */
export const recall = (memory: Memory, listing: FilmListing): string | undefined => {
  const entry = memory[listing.id];
  return entry &&
    entry.titleKey === titleKey(listing) &&
    sameRuntime(entry.runtimeMinutes, listing.runtimeMinutes)
    ? entry.filmId
    : undefined;
};

/** The memory after a run: today's certain links replace older ones; old ones fade out. */
export const remember = (
  memory: Memory,
  listings: FilmListing[],
  links: Map<string, { filmId: string; method: string }>,
  now: Date,
): Memory => {
  const next: Memory = Object.fromEntries(
    Object.entries(memory).filter(
      ([, entry]) => now.getTime() - Date.parse(entry.lastSeen) < FORGET_AFTER_MS,
    ),
  );
  for (const listing of listings) {
    const link = links.get(listing.id);
    const key = titleKey(listing);
    if (!link || link.method === "alias" || !key) {
      continue;
    }
    next[listing.id] = {
      filmId: link.filmId,
      titleKey: key,
      ...(listing.runtimeMinutes && { runtimeMinutes: listing.runtimeMinutes }),
      lastSeen: now.toISOString(),
    };
  }
  return next;
};

/** An unreadable or missing file is an empty memory: matching still works without it. */
export const loadMemory = async (path: string): Promise<Memory> => {
  try {
    const parsed = Memory.safeParse(JSON.parse(await readFile(path, "utf8")));
    return parsed.success ? parsed.data : {};
  } catch {
    return {};
  }
};

export const saveMemory = async (path: string, memory: Memory): Promise<void> => {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(memory, null, 2)}\n`);
};
