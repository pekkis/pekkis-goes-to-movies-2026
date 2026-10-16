import { readFileSync } from "node:fs";
import { SeriesKind, type ProviderBatch, type SeriesRef } from "@pgtm/model";
import { z } from "zod";
import { labelKey } from "../providers/labels.ts";
import { slugify } from "../providers/parsing.ts";

/**
 * The series registry, hand-maintained in config/series.json: strands, festivals,
 * retrospectives, clubs, distributor series, theme weeks (docs/classification.md#series).
 * Ids are stable; `aliases` are other spellings cinemas print.
 */
export const SeriesEntry = z.object({
  name: z.string().min(1),
  kind: SeriesKind,
  aliases: z.array(z.string().min(1)).optional(),
  note: z.string().optional(),
});
export const SeriesRegistry = z.record(z.string().regex(/^[a-z0-9-]+$/), SeriesEntry);
export type SeriesRegistry = z.infer<typeof SeriesRegistry>;

export const SERIES_PATH = new URL("../../config/series.json", import.meta.url);

/** Loaded once: parsers consult it like their site configs. */
export const SERIES: SeriesRegistry = SeriesRegistry.parse(
  JSON.parse(readFileSync(SERIES_PATH, "utf8")),
);

const byKey = (registry: SeriesRegistry) => {
  const index = new Map<string, string>();
  for (const [id, entry] of Object.entries(registry)) {
    for (const name of [entry.name, ...(entry.aliases ?? [])]) {
      index.set(labelKey(name), id);
    }
  }
  return index;
};
const INDEX = byKey(SERIES);

/** The registry id for a name a cinema prints, if the registry knows it. */
export const findSeries = (name: string, registry: SeriesRegistry = SERIES): string | undefined =>
  registry === SERIES ? INDEX.get(labelKey(name)) : byKey(registry).get(labelKey(name));

/**
 * Turns the series names a batch's screenings carry into ids, and lists them on the batch:
 * a registered name gets its registry id; any other name becomes the provider's own
 * strand, "{provider}/{slug}", until the registry takes it in.
 */
export const resolveSeries = (
  batch: ProviderBatch,
  registry: SeriesRegistry = SERIES,
): ProviderBatch => {
  const refs = new Map<string, SeriesRef>();
  const idOf = (name: string): string => {
    const known = findSeries(name, registry);
    if (known) {
      const entry = registry[known]!;
      refs.set(known, { id: known, name: entry.name, kind: entry.kind });
      return known;
    }
    const id = `${batch.provider.id}/${slugify(name)}`;
    if (!refs.has(id)) {
      refs.set(id, { id, name: name.trim(), kind: "strand" });
    }
    return id;
  };
  const screenings = batch.screenings.map((s) =>
    s.series.length === 0 ? s : { ...s, series: [...new Set(s.series.map(idOf))] },
  );
  return { ...batch, screenings, series: [...refs.values()] };
};
