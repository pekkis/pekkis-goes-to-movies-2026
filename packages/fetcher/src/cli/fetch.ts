import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { loadEnv } from "../lib/env.ts";
import { DATA_DIR } from "../lib/paths.ts";
import { helsinkiToday } from "../lib/time.ts";
import { runMatching } from "../matching/run.ts";
import { ProviderBatch } from "../model/schema.ts";
import { ADAPTERS } from "../providers/registry.ts";

const PROVIDERS = ADAPTERS.map((a) => a.id);

const USAGE = `Usage: pnpm pull [--provider ID ...] [--from YYYY-MM-DD] [--days N] [--venue ID ...] [--out DIR]

Fetches showtimes, writes raw snapshots and normalized batches as JSON, then matches films to TMDB.
Providers: ${PROVIDERS.join(", ")} (default: all). --venue takes source ids and needs exactly one --provider.
Finnkino opens a Chrome window for a few seconds when its 12-hour token needs renewing.`;

const { values } = parseArgs({
  options: {
    provider: { type: "string", multiple: true },
    from: { type: "string" },
    days: { type: "string", default: "7" },
    venue: { type: "string", multiple: true },
    out: { type: "string", default: DATA_DIR },
    help: { type: "boolean", short: "h" },
  },
});

if (values.help) {
  console.log(USAGE);
  process.exit(0);
}

// Fail before any request if the environment is incomplete.
const env = loadEnv();

const providers = values.provider ?? PROVIDERS;
const from = values.from ?? helsinkiToday();
const days = Number(values.days);
const invalid =
  !/^\d{4}-\d{2}-\d{2}$/.test(from) ||
  !Number.isInteger(days) ||
  days < 1 ||
  days > 90 ||
  providers.some((p) => !PROVIDERS.includes(p)) ||
  (values.venue !== undefined && providers.length !== 1);
if (invalid) {
  console.error(USAGE);
  process.exit(1);
}

const writeJson = async (path: string, data: unknown) => {
  await mkdir(join(path, ".."), { recursive: true });
  await writeFile(path, `${JSON.stringify(data, null, 2)}\n`);
  console.log(`wrote ${path}`);
};

let failures = 0;
for (const adapter of ADAPTERS.filter((a) => providers.includes(a.id))) {
  try {
    const { raw, batch } = await adapter.pull(
      { env, out: values.out },
      { from, days, ...(values.venue && { venues: values.venue }) },
    );
    const stamp = raw.fetchedAt.replace(/[:.]/g, "-");
    await writeJson(join(values.out, "raw", adapter.id, `${stamp}.json`), raw);
    // The parser already validates rows; this guards the output contract itself.
    ProviderBatch.parse(batch);
    await writeJson(join(values.out, "normalized", `${adapter.id}.json`), batch);

    const unmapped = new Set(batch.screenings.flatMap((s) => s.unmappedLabels));
    console.log(
      `${adapter.id}: ${batch.venues.length} venues, ${batch.listings.length} films, ` +
        `${batch.screenings.length} screenings, ${batch.warnings.length} warnings` +
        (unmapped.size ? `, unmapped labels: ${[...unmapped].join(", ")}` : ""),
    );
    for (const warning of batch.warnings) console.warn(`  [${warning.code}] ${warning.message}`);
  } catch (error) {
    failures++;
    console.error(
      `${adapter.id}: FAILED: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

await runMatching(values.out, env);
if (failures) process.exit(1);
