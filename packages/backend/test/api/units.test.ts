import { describe, expect, it } from "vitest";
import { parseBbox } from "../../src/api/params.ts";
import { toHelsinkiIso } from "../../src/lib/time.ts";
import { decodeCursor, encodeCursor } from "../../src/queries/screenings.ts";

describe("toHelsinkiIso", () => {
  it("uses the summer and winter offsets", () => {
    expect(toHelsinkiIso(new Date("2026-10-10T15:00:00Z"))).toBe("2026-10-10T18:00:00+03:00");
    expect(toHelsinkiIso(new Date("2026-12-24T22:30:00Z"))).toBe("2026-12-25T00:30:00+02:00");
  });
});

describe("parseBbox", () => {
  it("reads minLon,minLat,maxLon,maxLat", () => {
    expect(parseBbox("24.5,60.1,25.3,60.4")).toEqual({
      minLon: 24.5,
      minLat: 60.1,
      maxLon: 25.3,
      maxLat: 60.4,
    });
  });

  it("rejects inverted, short and out-of-range boxes", () => {
    expect(parseBbox("25.3,60.4,24.5,60.1")).toBeUndefined();
    expect(parseBbox("1,2,3")).toBeUndefined();
    expect(parseBbox("24,95,25,96")).toBeUndefined();
  });
});

describe("cursor", () => {
  it("round-trips and rejects garbage", () => {
    const cursor = { startsAt: "2026-10-10T15:00:00.000Z", id: "finnkino:show:1" };
    expect(decodeCursor(encodeCursor(cursor))).toEqual(cursor);
    expect(decodeCursor("bm9wZQ")).toBeUndefined();
  });
});
