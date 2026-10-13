/**
 * Dates and times, the one place for them: Helsinki wall-clock time, the programme day, and
 * calendar arithmetic, on Temporal (native in Node 26; the website loads temporal-polyfill
 * for browsers without it). Instants are ISO strings with an offset; calendar dates are
 * `YYYY-MM-DD`. Shared by the fetcher, the backend and the website (`@pgtm/model/time`).
 */

export const HELSINKI = "Europe/Helsinki";

/**
 * Shows starting before this hour belong to the previous day's programme ("business date"):
 * a 00:30 show is part of the evening before. Used when the source does not state the day.
 */
export const BUSINESS_DAY_CUTOFF_HOUR = 5;

/**
 * The current instant. Read through `Date.now()` rather than `Temporal.Now`, so tests can
 * fake the clock with ordinary fake timers.
 */
export const currentInstant = (): Temporal.Instant =>
  Temporal.Instant.fromEpochMilliseconds(Date.now());

const toInstant = (instant: string | Date | Temporal.Instant): Temporal.Instant =>
  instant instanceof Temporal.Instant
    ? instant
    : instant instanceof Date
      ? Temporal.Instant.fromEpochMilliseconds(instant.getTime())
      : Temporal.Instant.from(instant);

/** A zoned time as ISO with its offset and no zone name: `2026-10-09T20:00:00+03:00`. */
const isoWithOffset = (t: Temporal.ZonedDateTime): string =>
  t.toString({ timeZoneName: "never", smallestUnit: "second" });

/**
 * An instant (ISO string with an offset, or a `Date` from the database) as Helsinki
 * wall-clock time with its offset, e.g. `2026-10-09T20:00:00+03:00`. Throws on invalid input.
 */
export const toHelsinkiIso = (instant: string | Date): string => {
  if (instant instanceof Date && Number.isNaN(instant.getTime())) {
    throw new RangeError("Invalid date");
  }
  return isoWithOffset(toInstant(instant).toZonedDateTimeISO(HELSINKI));
};

/** The calendar date in Helsinki at an instant (default: now), as `YYYY-MM-DD`. */
export const helsinkiToday = (now: string | Date | Temporal.Instant = currentInstant()): string =>
  toInstant(now).toZonedDateTimeISO(HELSINKI).toPlainDate().toString();

/** `YYYY-MM-DD` plus (or minus) whole days: "2026-10-31", 1 -> "2026-11-01". */
export const addDays = (date: string, days: number): string =>
  Temporal.PlainDate.from(date).add({ days }).toString();

/** Calendar days from `from` to `to` (negative when `to` is earlier). */
export const daysBetween = (from: string, to: string): number =>
  Temporal.PlainDate.from(from).until(Temporal.PlainDate.from(to), { largestUnit: "days" }).days;

/** Whether `value` is a real `YYYY-MM-DD` date (no 31.2., no other formats). */
export const isIsoDate = (value: string): boolean => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  try {
    Temporal.PlainDate.from(value, { overflow: "reject" });
    return true;
  } catch {
    return false;
  }
};

/** The inclusive business-date window `[from, from + days - 1]`. */
export const dateWindow = (from: string, days: number): { from: string; to: string } => ({
  from,
  to: addDays(from, days - 1),
});

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
 * impossible values (31.2., 25:00) and for times the clock skips when summer time starts,
 * instead of letting them roll over. A time that occurs twice in autumn takes the first.
 */
export const helsinkiShowTime = (t: LocalDateTime): ShowTime | undefined => {
  let start: Temporal.ZonedDateTime;
  try {
    start = Temporal.ZonedDateTime.from(
      { ...t, second: t.second ?? 0, timeZone: HELSINKI },
      { overflow: "reject", disambiguation: "compatible" },
    );
  } catch {
    return undefined;
  }
  // "compatible" moves a skipped time forward; that wall clock doesn't exist, so reject it.
  if (start.hour !== t.hour || start.minute !== t.minute) {
    return undefined;
  }
  const day = start.toPlainDate();
  const business = t.hour < BUSINESS_DAY_CUTOFF_HOUR ? day.subtract({ days: 1 }) : day;
  return { startsAt: isoWithOffset(start), businessDate: business.toString() };
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
  let local: Temporal.ZonedDateTime;
  try {
    local = Temporal.Instant.from(instant).toZonedDateTimeISO(HELSINKI);
  } catch {
    return undefined;
  }
  return helsinkiShowTime({
    year: local.year,
    month: local.month,
    day: local.day,
    hour: local.hour,
    minute: local.minute,
    second: local.second,
  });
};

/** Whole minutes from `now` until `instant`, rounded up (negative once it has passed). */
export const minutesUntil = (instant: string, now: Temporal.Instant): number =>
  Math.ceil((Temporal.Instant.from(instant).epochMilliseconds - now.epochMilliseconds) / 60_000);
