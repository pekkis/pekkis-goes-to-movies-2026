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
