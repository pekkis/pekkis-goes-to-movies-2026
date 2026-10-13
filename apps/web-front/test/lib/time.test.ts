import { describe, expect, it } from "vitest";
import { addDays, formatDay, formatTime, isIsoDate } from "../../src/lib/time.ts";

describe("formatTime", () => {
  it.each([
    ["2026-10-13T18:00:00+03:00", "18.00"],
    ["2026-10-13T15:00:00Z", "18.00"], // summer time: UTC+3
    ["2026-12-01T16:30:00Z", "18.30"], // winter time: UTC+2
    ["2026-10-14T00:30:00+03:00", "00.30"], // after midnight
  ])("%s -> %s in Helsinki", (iso, expected) => {
    expect(formatTime(iso)).toBe(expected);
  });
});

describe("days", () => {
  it("formats a day in Finnish", () => {
    expect(formatDay("2026-10-13")).toBe("tiistaina 13.10.");
  });

  it.each([
    ["2026-10-13", 1, "2026-10-14"],
    ["2026-10-31", 1, "2026-11-01"],
    ["2026-03-01", -1, "2026-02-28"],
    ["2026-10-25", 1, "2026-10-26"], // across the switch to winter time
  ])("%s %+d -> %s", (date, days, expected) => {
    expect(addDays(date, days)).toBe(expected);
  });

  it.each([
    ["2026-10-13", true],
    ["2026-02-31", false],
    ["13.10.2026", false],
    ["", false],
  ])("isIsoDate(%j) is %s", (value, expected) => {
    expect(isIsoDate(value)).toBe(expected);
  });
});
