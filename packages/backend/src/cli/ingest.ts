import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { FilmCatalog, ProviderBatch } from "@pgtm/model";
import { createDb } from "../db/database.ts";
import { ingestBatch, ingestFilms } from "../ingest/ingest.ts";
import { loadEnv } from "../lib/env.ts";
import { NORMALIZED_DIR } from "../lib/paths.ts";

const CATALOG = "films.json";

const { values } = parseArgs({
  options: { dir: { type: "string", default: NORMALIZED_DIR } },
});

const env = loadEnv();
const readJson = async (file: string): Promise<unknown> =>
  JSON.parse(await readFile(join(values.dir, file), "utf8"));

// Validate everything before touching the database.
const files = (await readdir(values.dir)).filter((f) => f.endsWith(".json"));
const validate = async <T>(
  file: string,
  schema: {
    safeParse: (v: unknown) => { success: true; data: T } | { success: false; error: Error };
  },
): Promise<T> => {
  const result = schema.safeParse(await readJson(file));
  if (result.success) return result.data;
  console.error(
    `${file} does not match the model (stale data? run \`pnpm pull\`):\n${result.error.message}`,
  );
  process.exit(1);
};
const catalog = files.includes(CATALOG) ? await validate(CATALOG, FilmCatalog) : undefined;
const batches = await Promise.all(
  files
    .filter((f) => f !== CATALOG)
    .map(async (f) => ({ file: f, batch: await validate(f, ProviderBatch) })),
);

const db = createDb(env.DATABASE_URL);
try {
  if (catalog) console.log(`films: ${await ingestFilms(db, catalog)} upserted`);
  for (const { file, batch } of batches) {
    const result = await ingestBatch(db, batch);
    console.log(
      `${batch.provider.id} (${file}): ${result.inserted} new, ${result.updated} updated, ${result.removed} removed screenings`,
    );
  }
} finally {
  await db.destroy();
}
