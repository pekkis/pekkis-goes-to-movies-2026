import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { loadEnv, requireTmdbKey } from "../lib/env.ts";
import { DATA_DIR } from "../lib/paths.ts";
import { helsinkiToday, isIsoDate } from "@pgtm/model/time";
import { runMatching } from "../matching/run.ts";
import { ProviderBatch } from "@pgtm/model";
import { finishVenues, loadVenueOverrides } from "../providers/overrides.ts";
import { deriveTags } from "../providers/labels.ts";
import { resolveSeries } from "../series/registry.ts";
import { paintFor } from "../lib/paint.ts";
import { batchReport, failureReport, progressReport, summaryReport, tookReport } from "./report.ts";
import PQueue from "p-queue";
import { ADAPTERS, selectAdapters, type Adapter } from "../providers/registry.ts";

// Each stream is coloured only when it is a terminal.
const paintOut = paintFor(process.stdout);
const paintErr = paintFor(process.stderr);

/** How often a running pull says what it is still waiting for. */
const PROGRESS_EVERY_MS = 30_000;

/** Providers pulled at the same time (each on its own host, paced per host). */
const CONCURRENCY = 6;

const PROVIDERS = ADAPTERS.map((a) => a.id);
const PLATFORMS = [...new Set(ADAPTERS.map((a) => a.platform))];

const USAGE = `Usage: pnpm pull [--provider ID ...] [--from YYYY-MM-DD] [--days N] [--venue ID ...] [--out DIR]

Fetches showtimes, writes raw snapshots and normalized batches as JSON, then matches films to TMDB.
Providers: ${PROVIDERS.join(", ")} (default: all).
A platform name selects all of its providers: ${PLATFORMS.join(", ")}.
--venue takes source ids or venue slugs and needs exactly one provider.
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
requireTmdbKey(env);

const selected = selectAdapters(values.provider);
const from = values.from ?? helsinkiToday();
const days = Number(values.days);
const invalid =
  !isIsoDate(from) ||
  !Number.isInteger(days) ||
  days < 1 ||
  days > 90 ||
  selected === undefined ||
  (values.venue !== undefined && selected.length !== 1);
if (invalid) {
  console.error(USAGE);
  process.exit(1);
}

const writeJson = async (path: string, data: unknown) => {
  await mkdir(join(path, ".."), { recursive: true });
  await writeFile(path, `${JSON.stringify(data, null, 2)}\n`);
};

const overrides = await loadVenueOverrides();

/**
 * Pulls one adapter and returns its report. Adapters run concurrently (different hosts;
 * each adapter still paces its own host), so output is collected and printed as a block.
 */
const pullOne = async (adapter: Adapter): Promise<{ ok: boolean; lines: string[] }> => {
  try {
    const pulled = await adapter.pull(
      { env, out: values.out },
      { from, days, ...(values.venue && { venues: values.venue }) },
    );
    const { raw } = pulled;
    const batch = deriveTags(resolveSeries(finishVenues(pulled.batch, overrides)));
    const stamp = raw.fetchedAt.replace(/[:.]/g, "-");
    await writeJson(join(values.out, "raw", adapter.id, `${stamp}.json`), raw);
    // The parser already validates rows; this guards the output contract itself.
    ProviderBatch.parse(batch);
    await writeJson(join(values.out, "normalized", `${adapter.id}.json`), batch);

    return { ok: true, lines: batchReport(adapter.id, batch, paintOut) };
  } catch (error) {
    return { ok: false, lines: [failureReport(adapter.id, error, paintErr)] };
  }
};

const queue = new PQueue({ concurrency: CONCURRENCY });
const total = selected?.length ?? 0;
let done = 0;
/** Providers being pulled now, with when they started: what a slow pull is waiting for. */
const running = new Map<string, number>();
const progress = setInterval(() => {
  console.log(progressReport(done, total, running, Date.now(), paintOut));
}, PROGRESS_EVERY_MS);
const results = await Promise.all(
  (selected ?? []).map((adapter) =>
    queue.add(async () => {
      const started = Date.now();
      running.set(adapter.id, started);
      const result = await pullOne(adapter);
      running.delete(adapter.id);
      done++;
      const lines = [`${result.lines[0]} ${tookReport(Date.now() - started, paintOut)}`];
      (result.ok ? console.log : console.error)([...lines, ...result.lines.slice(1)].join("\n"));
      return result;
    }),
  ),
);
clearInterval(progress);
const failures = results.filter((r) => !r.ok).length;
console.log(summaryReport(results.length - failures, results.length, values.out, paintOut));

// Matching needs at least one fresh batch, and a TMDB outage must not hide what was pulled.
if (failures < results.length) {
  try {
    await runMatching(values.out, env);
  } catch (error) {
    console.error(failureReport("tmdb: matching", error, paintErr));
    process.exitCode = 1;
  }
}
if (failures) {
  process.exitCode = 1;
}
