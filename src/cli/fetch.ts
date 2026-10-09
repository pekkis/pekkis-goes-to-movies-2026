import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { loadEnv } from "../lib/env.ts";
import { createHttpClient } from "../lib/http.ts";
import { helsinkiToday } from "../lib/time.ts";
import { runMatching } from "../matching/run.ts";
import { ProviderBatch } from "../model/schema.ts";
import { fetchBiorex } from "../providers/biorex/fetch.ts";
import { parseBiorex } from "../providers/biorex/parse.ts";

const USAGE = `Usage: pnpm pull [--from YYYY-MM-DD] [--days N] [--cinema ID ...] [--out DIR]

Fetches BioRex showtimes, writes the raw snapshot and the normalized batch as JSON.`;

const { values } = parseArgs({
  options: {
    from: { type: "string" },
    days: { type: "string", default: "7" },
    cinema: { type: "string", multiple: true },
    out: { type: "string", default: "data" },
    help: { type: "boolean", short: "h" },
  },
});

if (values.help) {
  console.log(USAGE);
  process.exit(0);
}

// Fail before any request if the environment is incomplete.
const env = loadEnv();

const from = values.from ?? helsinkiToday();
const days = Number(values.days);
if (!/^\d{4}-\d{2}-\d{2}$/.test(from) || !Number.isInteger(days) || days < 1 || days > 31) {
  console.error(USAGE);
  process.exit(1);
}
const cinemaIds = values.cinema?.map(Number);

const writeJson = async (path: string, data: unknown) => {
  await mkdir(join(path, ".."), { recursive: true });
  await writeFile(path, `${JSON.stringify(data, null, 2)}\n`);
  console.log(`wrote ${path}`);
};

const http = createHttpClient(env.CONTACT ? { contact: env.CONTACT } : {});
const raw = await fetchBiorex(http, { from, days, ...(cinemaIds && { cinemaIds }) });
const stamp = raw.fetchedAt.replace(/[:.]/g, "-");
await writeJson(join(values.out, "raw", "biorex", `${stamp}.json`), raw);

const batch = parseBiorex(raw);
// The parser already validates rows; this guards the output contract itself.
ProviderBatch.parse(batch);
await writeJson(join(values.out, "normalized", "biorex.json"), batch);

const unmapped = new Set(batch.screenings.flatMap((s) => s.unmappedLabels));
console.log(
  `biorex: ${batch.venues.length} venues, ${batch.listings.length} films, ` +
    `${batch.screenings.length} screenings, ${batch.warnings.length} warnings` +
    (unmapped.size ? `, unmapped labels: ${[...unmapped].join(", ")}` : ""),
);
for (const warning of batch.warnings) console.warn(`  [${warning.code}] ${warning.message}`);

await runMatching(values.out, env);
