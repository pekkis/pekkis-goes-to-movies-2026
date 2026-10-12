import { describe, expect, it } from "vitest";
import {
  dateWindow,
  helsinkiShowTime,
  helsinkiShowTimeAt,
  helsinkiToday,
  parseLocalDateTime,
  toHelsinkiIso,
} from "../../src/lib/time.ts";

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
