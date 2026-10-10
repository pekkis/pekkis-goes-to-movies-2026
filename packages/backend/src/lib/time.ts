const HELSINKI = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Helsinki",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
  timeZoneName: "longOffset",
});

/** A timestamp as Helsinki local time with its offset: "2026-10-10T18:00:00+03:00". */
export const toHelsinkiIso = (date: Date): string => {
  const p = Object.fromEntries(HELSINKI.formatToParts(date).map((x) => [x.type, x.value]));
  // timeZoneName is "GMT+03:00" (or "GMT" at offset zero, which Helsinki never has).
  const offset = p["timeZoneName"]!.replace("GMT", "") || "+00:00";
  return `${p["year"]}-${p["month"]}-${p["day"]}T${p["hour"]}:${p["minute"]}:${p["second"]}${offset}`;
};
