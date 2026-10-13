import { describe, expect, it } from "vitest";
import { formatDay, formatTime } from "../../src/lib/time.ts";

// Date arithmetic (addDays, isIsoDate, …) is shared: tested in packages/model/test/time.test.ts.

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

describe("formatDay", () => {
  it("formats a day in Finnish", () => {
    expect(formatDay("2026-10-13")).toBe("tiistaina 13.10.");
  });
});
