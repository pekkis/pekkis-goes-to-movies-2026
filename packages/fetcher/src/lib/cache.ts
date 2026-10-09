import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

export type JsonCache = {
  /** Returns the cached value if younger than `maxAgeMs`, otherwise calls `load` and stores the result. */
  get: <T>(key: string, maxAgeMs: number, load: () => Promise<T>) => Promise<T>;
};

type Entry = { storedAt: string; key: string; value: unknown };

/** File-per-key JSON cache. Keys are hashed, the original key is kept inside for debugging. */
export const createDiskCache = (dir: string, now: () => Date = () => new Date()): JsonCache => ({
  get: async <T>(key: string, maxAgeMs: number, load: () => Promise<T>): Promise<T> => {
    const path = join(dir, `${createHash("sha1").update(key).digest("hex")}.json`);
    try {
      const entry = JSON.parse(await readFile(path, "utf8")) as Entry;
      if (now().getTime() - Date.parse(entry.storedAt) < maxAgeMs) return entry.value as T;
    } catch {
      // missing or unreadable: fall through and load
    }
    const value = await load();
    await mkdir(dir, { recursive: true });
    const entry: Entry = { storedAt: now().toISOString(), key, value };
    await writeFile(path, JSON.stringify(entry));
    return value;
  },
});

/** For tests and dry runs. */
export const noCache: JsonCache = { get: (_key, _maxAgeMs, load) => load() };
