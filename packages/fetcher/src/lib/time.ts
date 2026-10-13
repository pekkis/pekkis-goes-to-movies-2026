import { TZDate } from "@date-fns/tz";
import { addDays, formatISO, parseISO, subDays } from "date-fns";

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

/** The inclusive business-date window `[from, from + days - 1]`. */
export const dateWindow = (from: string, days: number): { from: string; to: string } => ({
  from,
  to: formatISO(addDays(parseISO(from), days - 1), { representation: "date" }),
});

/**
 * Shows starting before this hour belong to the previous day's programme ("business date"):
 * a 00:30 show is part of the evening before. Used when the source does not state the day.
 */
export const BUSINESS_DAY_CUTOFF_HOUR = 5;

export type LocalDateTime = {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second?: number;
};

export type ShowTime = { startsAt: string; businessDate: string };

/**
 * Helsinki wall-clock time -> ISO start with offset and the programme day. Undefined for
 * impossible values (31.2., 25:00) instead of letting them roll over into another day.
 */
export const helsinkiShowTime = (t: LocalDateTime): ShowTime | undefined => {
  const start = new TZDate(t.year, t.month - 1, t.day, t.hour, t.minute, t.second ?? 0, FINNISH_TZ);
  const valid =
    !Number.isNaN(start.getTime()) &&
    start.getFullYear() === t.year &&
    start.getMonth() === t.month - 1 &&
    start.getDate() === t.day &&
    start.getHours() === t.hour &&
    start.getMinutes() === t.minute;
  if (!valid) {
    return undefined;
  }
  const business = t.hour < BUSINESS_DAY_CUTOFF_HOUR ? subDays(start, 1) : start;
  return {
    startsAt: formatISO(start),
    businessDate: formatISO(business, { representation: "date" }),
  };
};

/** "2026-10-14 19:00" or "2026-10-14 19:00:00", Helsinki local -> parts. */
export const parseLocalDateTime = (raw: string): LocalDateTime | undefined => {
  const m = raw.trim().match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) {
    return undefined;
  }
  const [year, month, day, hour, minute] = m.slice(1, 6).map(Number) as [
    number,
    number,
    number,
    number,
    number,
  ];
  return { year, month, day, hour, minute, ...(m[6] && { second: Number(m[6]) }) };
};

/** An instant with any offset -> the same show time in Helsinki, normalized. */
export const helsinkiShowTimeAt = (instant: string): ShowTime | undefined => {
  const local = new TZDate(parseISO(instant), FINNISH_TZ);
  if (Number.isNaN(local.getTime())) {
    return undefined;
  }
  return helsinkiShowTime({
    year: local.getFullYear(),
    month: local.getMonth() + 1,
    day: local.getDate(),
    hour: local.getHours(),
    minute: local.getMinutes(),
    second: local.getSeconds(),
  });
};
