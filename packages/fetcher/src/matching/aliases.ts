import { readFile } from "node:fs/promises";
import { z } from "zod";
import { Id } from "@pgtm/model";

/**
 * Hand-maintained overrides, committed to the repo: listing id -> TMDB id.
 * `tmdb: null` means "known not to be on TMDB, stop trying".
 */
export const Aliases = z.record(
  Id,
  z.object({
    tmdb: z.number().int().positive().nullable(),
    /** The listing's title, so that the file is readable. */
    title: z.string(),
    note: z.string().optional(),
  }),
);
export type Aliases = z.infer<typeof Aliases>;

export const ALIASES_PATH = new URL("../../config/tmdb-aliases.json", import.meta.url);

export const loadAliases = async (path: URL | string = ALIASES_PATH): Promise<Aliases> =>
  Aliases.parse(JSON.parse(await readFile(path, "utf8")));
