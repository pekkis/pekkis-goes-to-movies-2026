import { describe, expect, it } from "vitest";
import { helsinkiToday, toHelsinkiIso } from "../../src/lib/time.ts";

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
