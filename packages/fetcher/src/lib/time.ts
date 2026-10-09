import { TZDate } from "@date-fns/tz";
import { formatISO } from "date-fns";

export const FINNISH_TZ = "Europe/Helsinki";

/** UTC instant (any ISO string) -> Helsinki wall-clock with offset, e.g. `2026-10-09T20:00:00+03:00`. */
export const toHelsinkiIso = (instant: string): string => {
  const date = new TZDate(instant, FINNISH_TZ);
  if (Number.isNaN(date.getTime())) {
    throw new RangeError(`Invalid date: ${instant}`);
  }
  return formatISO(date);
};

/** Today's date in Helsinki as `YYYY-MM-DD`. */
export const helsinkiToday = (now: Date = new Date()): string =>
  formatISO(new TZDate(now, FINNISH_TZ), { representation: "date" });
