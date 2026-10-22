import "./temporal.ts";
import { HELSINKI } from "@pgtm/model/time";

// Temporal parses and computes; Intl prints. One formatter each, with explicit options,
// so native Temporal and the polyfill give the same text ("00.30", not "0.30").
const clock = new Intl.DateTimeFormat("fi-FI", {
  timeZone: HELSINKI,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const weekday = new Intl.DateTimeFormat("fi-FI", {
  timeZone: "UTC",
  weekday: "long",
  day: "numeric",
  month: "numeric",
});

/** "2026-10-13T18:00:00+03:00" -> "18.00", in Helsinki whatever the server's zone. */
export const formatTime = (iso: string): string =>
  clock.format(Temporal.Instant.from(iso).epochMilliseconds);

/** "2026-10-13" -> "tiistaina 13.10." (on Tuesday 13 October). */
export const formatDay = (date: string): string =>
  weekday.format(
    Temporal.PlainDate.from(date).toZonedDateTime({ timeZone: "UTC" }).epochMilliseconds,
  );

const shortDay = new Intl.DateTimeFormat("fi-FI", {
  timeZone: "UTC",
  weekday: "short",
  day: "numeric",
  month: "numeric",
});

/** "2026-10-19" -> "ma 19.10." (for the search page's day checkboxes). */
export const formatShortDay = (date: string): string =>
  shortDay.format(
    Temporal.PlainDate.from(date).toZonedDateTime({ timeZone: "UTC" }).epochMilliseconds,
  );

/**
 * Days, in order, as short as they read: "pe 23.10.", a run as "pe 23.10.–su 25.10.",
 * anything else as a list "pe 23.10., su 25.10.".
 */
export const formatDayRange = (days: readonly string[]): string => {
  const sorted = days.toSorted();
  const consecutive = sorted.every(
    (day, i) =>
      i === 0 ||
      Temporal.PlainDate.from(sorted[i - 1]!)
        .add({ days: 1 })
        .toString() === day,
  );
  if (sorted.length > 1 && consecutive) {
    return `${formatShortDay(sorted[0]!)}–${formatShortDay(sorted.at(-1)!)}`;
  }
  return sorted.map(formatShortDay).join(", ");
};

const fullDate = new Intl.DateTimeFormat("fi-FI", {
  timeZone: "UTC",
  day: "numeric",
  month: "numeric",
  year: "numeric",
});

/** "2026-10-23" -> "23.10.2026". */
export const formatDate = (date: string): string =>
  fullDate.format(
    Temporal.PlainDate.from(date).toZonedDateTime({ timeZone: "UTC" }).epochMilliseconds,
  );
