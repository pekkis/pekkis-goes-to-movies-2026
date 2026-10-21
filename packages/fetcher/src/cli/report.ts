import { DATA_MISSING_WARNING, type ProviderBatch } from "@pgtm/model";
import type { Paint } from "../lib/paint.ts";

// The pull's report lines, painted (lib/paint.ts).

const count = (n: number, noun: string) => `${n} ${noun}`;

/** One provider's lines: counts, unmapped labels, then each warning. */
export const batchReport = (id: string, batch: ProviderBatch, paint: Paint): string[] => {
  const unmapped = [...new Set(batch.screenings.flatMap((s) => s.unmappedLabels))];
  const warnings = batch.warnings.length;
  const parts = [
    count(batch.venues.length, "venues"),
    count(batch.listings.length, "films"),
    // Nothing at all is worth a look, though a cinema may simply be closed.
    batch.screenings.length === 0
      ? paint("yellow", count(0, "screenings"))
      : count(batch.screenings.length, "screenings"),
    warnings ? paint("yellow", count(warnings, "warnings")) : count(0, "warnings"),
    ...(unmapped.length ? [paint("cyan", `unmapped labels: ${unmapped.join(", ")}`)] : []),
  ];
  return [
    `${paint("bold", id)}: ${parts.join(", ")}`,
    ...batch.warnings.map((w) => {
      // Data missing (screenings may be lost) is red; deliberate skips are yellow.
      const colour = DATA_MISSING_WARNING.test(w.code) ? "red" : "yellow";
      return `  ${paint(colour, `[${w.code}]`)} ${w.message}`;
    }),
  ];
};

export const failureReport = (id: string, error: unknown, paint: Paint): string =>
  `${paint("bold", id)}: ${paint(["red", "bold"], "FAILED")}: ${error instanceof Error ? error.message : String(error)}`;

export const summaryReport = (pulled: number, total: number, out: string, paint: Paint): string =>
  paint(pulled === total ? "green" : ["red", "bold"], `pulled ${pulled} of ${total} providers`) +
  ` into ${out}`;

/** "12 s", "4 min 05 s". */
const duration = (ms: number) => {
  const seconds = Math.round(ms / 1000);
  return seconds < 60
    ? `${seconds} s`
    : `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, "0")} s`;
};

/** How long one provider took, after its line; slow ones in yellow. */
export const tookReport = (ms: number, paint: Paint): string =>
  ms >= 60_000 ? paint("yellow", `(${duration(ms)})`) : `(${duration(ms)})`;

/**
 * A running pull's progress: how many are done, and which providers are still being
 * pulled and for how long, longest first. A stuck source shows by name.
 */
export const progressReport = (
  done: number,
  total: number,
  running: ReadonlyMap<string, number>,
  now: number,
  paint: Paint,
): string => {
  const waiting = [...running]
    .toSorted(([, a], [, b]) => a - b)
    .map(([id, started]) => {
      const ms = now - started;
      const text = `${id} ${duration(ms)}`;
      return ms >= 120_000 ? paint("yellow", text) : text;
    });
  return (
    paint("cyan", `… ${done} of ${total} done`) +
    (waiting.length ? `; running: ${waiting.join(", ")}` : "")
  );
};
