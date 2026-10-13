const ZONE = "Europe/Helsinki";

const clock = new Intl.DateTimeFormat("fi-FI", {
  timeZone: ZONE,
  hour: "2-digit",
  minute: "2-digit",
});

const day = new Intl.DateTimeFormat("fi-FI", {
  timeZone: ZONE,
  weekday: "long",
  day: "numeric",
  month: "numeric",
});

/** "2026-10-13T18:00:00+03:00" -> "18.00", in Helsinki whatever the server's zone. */
export const formatTime = (iso: string): string => clock.format(new Date(iso));

/** Noon UTC of a calendar date: the same day in every European zone. */
const noon = (date: string) => new Date(`${date}T12:00:00Z`);

/** "2026-10-13" -> "tiistaina 13.10." (on Tuesday 13 October). */
export const formatDay = (date: string): string => day.format(noon(date));

/** "2026-10-13", +1 -> "2026-10-14". */
export const addDays = (date: string, days: number): string => {
  const d = noon(date);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
};

export const isIsoDate = (value: string): boolean =>
  /^\d{4}-\d{2}-\d{2}$/.test(value) && noon(value).toISOString().startsWith(value);
