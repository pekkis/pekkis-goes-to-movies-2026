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
