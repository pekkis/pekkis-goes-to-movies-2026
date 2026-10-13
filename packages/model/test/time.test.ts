import { describe, expect, it, vi } from "vitest";
import {
  addDays,
  currentInstant,
  dateWindow,
  daysBetween,
  helsinkiShowTime,
  helsinkiShowTimeAt,
  helsinkiToday,
  isIsoDate,
  minutesUntil,
  nearestDate,
  parseLocalDateTime,
  toHelsinkiIso,
} from "../src/time.ts";

describe("toHelsinkiIso", () => {
  it("uses +03:00 in summer time", () => {
    expect(toHelsinkiIso("2026-10-09T17:00:00.000Z")).toBe("2026-10-09T20:00:00+03:00");
  });

  it("uses +02:00 in winter time", () => {
    expect(toHelsinkiIso("2026-12-15T19:00:00.000Z")).toBe("2026-12-15T21:00:00+02:00");
  });

  it("handles the repeated hour when summer time ends (2026-10-25)", () => {
    expect(toHelsinkiIso("2026-10-25T00:30:00.000Z")).toBe("2026-10-25T03:30:00+03:00");
    expect(toHelsinkiIso("2026-10-25T01:30:00.000Z")).toBe("2026-10-25T03:30:00+02:00");
  });

  it("rejects garbage", () => {
    expect(() => toHelsinkiIso("not a date")).toThrow(RangeError);
  });
});

describe("helsinkiToday", () => {
  it("is already the next day in Helsinki late in the UTC evening", () => {
    expect(helsinkiToday(new Date("2026-10-09T22:30:00.000Z"))).toBe("2026-10-10");
  });
});

describe("dateWindow", () => {
  it("is inclusive and crosses month ends", () => {
    expect(dateWindow("2026-10-09", 1)).toEqual({ from: "2026-10-09", to: "2026-10-09" });
    expect(dateWindow("2026-10-29", 7)).toEqual({ from: "2026-10-29", to: "2026-11-04" });
  });
});

describe("helsinkiShowTime", () => {
  it("gives the start with offset and the programme day", () => {
    expect(helsinkiShowTime({ year: 2026, month: 10, day: 14, hour: 19, minute: 0 })).toEqual({
      startsAt: "2026-10-14T19:00:00+03:00",
      businessDate: "2026-10-14",
    });
  });

  it("counts shows before 05:00 to the previous day, across the DST change", () => {
    expect(helsinkiShowTime({ year: 2026, month: 10, day: 25, hour: 0, minute: 30 })).toEqual({
      startsAt: "2026-10-25T00:30:00+03:00",
      businessDate: "2026-10-24",
    });
    expect(
      helsinkiShowTime({ year: 2026, month: 10, day: 26, hour: 4, minute: 59 })?.businessDate,
    ).toBe("2026-10-25");
  });

  it("rejects impossible dates instead of rolling them over", () => {
    expect(
      helsinkiShowTime({ year: 2026, month: 2, day: 31, hour: 18, minute: 0 }),
    ).toBeUndefined();
    expect(
      helsinkiShowTime({ year: 2026, month: 10, day: 10, hour: 25, minute: 0 }),
    ).toBeUndefined();
  });

  it("reads local date-times with or without seconds, and instants with any offset", () => {
    expect(parseLocalDateTime("2026-10-14 19:00")).toEqual({
      year: 2026,
      month: 10,
      day: 14,
      hour: 19,
      minute: 0,
    });
    expect(parseLocalDateTime("2026-10-14 19:00:30")?.second).toBe(30);
    expect(parseLocalDateTime("14.10.2026 19:00")).toBeUndefined();
    expect(helsinkiShowTimeAt("2026-10-10T11:00:00Z")).toEqual({
      startsAt: "2026-10-10T14:00:00+03:00",
      businessDate: "2026-10-10",
    });
  });
});

describe("calendar dates", () => {
  it.each([
    ["2026-10-31", 1, "2026-11-01"],
    ["2026-03-01", -1, "2026-02-28"],
    ["2028-02-28", 1, "2028-02-29"],
    ["2026-10-25", 1, "2026-10-26"], // across the end of summer time
  ])("addDays(%s, %d) = %s", (date, days, expected) => {
    expect(addDays(date, days)).toBe(expected);
  });

  it("counts calendar days between dates, in either direction", () => {
    expect(daysBetween("2026-10-13", "2026-10-20")).toBe(7);
    expect(daysBetween("2026-10-20", "2026-10-13")).toBe(-7);
    expect(daysBetween("2026-03-28", "2026-03-30")).toBe(2); // across the start of summer time
  });

  it.each([
    ["2026-10-13", true],
    ["2028-02-29", true],
    ["2026-02-31", false],
    ["13.10.2026", false],
    ["2026-1-3", false],
    ["", false],
  ])("isIsoDate(%j) is %s", (value, expected) => {
    expect(isIsoDate(value)).toBe(expected);
  });
});

describe("instants", () => {
  it("formats a database Date in Helsinki like an ISO string", () => {
    expect(toHelsinkiIso(new Date("2026-10-09T17:00:00.000Z"))).toBe("2026-10-09T20:00:00+03:00");
    expect(() => toHelsinkiIso(new Date("nope"))).toThrow(RangeError);
  });

  it("rejects the hour the clock skips when summer time starts (2027-03-28 03:00→04:00)", () => {
    const at = (hour: number) =>
      helsinkiShowTime({ year: 2027, month: 3, day: 28, hour, minute: 30 });
    expect(at(3)).toBeUndefined();
    expect(at(4)?.startsAt).toBe("2027-03-28T04:30:00+03:00");
  });

  it("counts minutes until an instant, rounding up", () => {
    const now = Temporal.Instant.from("2026-10-13T09:00:00Z");
    expect(minutesUntil("2026-10-13T12:30:00+03:00", now)).toBe(30);
    expect(minutesUntil("2026-10-13T12:00:30+03:00", now)).toBe(1);
    expect(minutesUntil("2026-10-13T11:45:00+03:00", now)).toBe(-15);
  });

  it("reads the current instant through Date.now(), so fake timers control it", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-13T09:00:00Z"));
    expect(currentInstant().toString()).toBe("2026-10-13T09:00:00Z");
    vi.useRealTimers();
  });
});

describe("nearestDate", () => {
  it.each([
    [14, 10, "2026-10-13", "2026-10-14"],
    [15, 12, "2026-10-13", "2026-12-15"],
    [3, 1, "2026-10-13", "2027-01-03"], // the programme reaches into next year
    [20, 9, "2026-10-13", "2026-09-20"], // a few weeks back is still this year
    [30, 12, "2027-01-05", "2026-12-30"], // early January looking back at December
    [29, 2, "2027-12-01", "2028-02-29"], // only a leap year has it
  ])("%d.%d. near %s is %s", (day, month, reference, expected) => {
    expect(nearestDate(day, month, reference)).toBe(expected);
  });

  it("rejects impossible dates, and ones no nearby year has", () => {
    expect(nearestDate(31, 2, "2026-10-13")).toBeUndefined();
    expect(nearestDate(29, 2, "2026-10-13")).toBeUndefined(); // 2027 is no leap year
  });
});
