import { describe, expect, it } from "vitest";
import { bboxAround, distanceKm } from "../src/geo.ts";

const HELSINKI = { lat: 60.1699, lon: 24.9384 };
const TAMPERE = { lat: 61.4978, lon: 23.761 };

describe("distanceKm", () => {
  it("measures known distances", () => {
    expect(distanceKm(HELSINKI, TAMPERE)).toBeCloseTo(160.5, 0);
    expect(distanceKm(HELSINKI, HELSINKI)).toBe(0);
    expect(distanceKm(TAMPERE, HELSINKI)).toBeCloseTo(distanceKm(HELSINKI, TAMPERE), 9);
  });
});

describe("bboxAround", () => {
  it("holds every point within the radius, in the API's order", () => {
    const [minLon, minLat, maxLon, maxLat] = bboxAround(TAMPERE, 25);
    expect(minLon).toBeLessThan(TAMPERE.lon);
    expect(maxLat).toBeGreaterThan(TAMPERE.lat);
    // Due north, east, south and west at 24.9 km all fall inside.
    for (const [dLat, dLon] of [
      [0.2235, 0],
      [0, 0.467],
      [-0.2235, 0],
      [0, -0.467],
    ] as const) {
      const p = { lat: TAMPERE.lat + dLat, lon: TAMPERE.lon + dLon };
      expect(distanceKm(TAMPERE, p)).toBeLessThan(25);
      expect(p.lon).toBeGreaterThan(minLon);
      expect(p.lon).toBeLessThan(maxLon);
      expect(p.lat).toBeGreaterThan(minLat);
      expect(p.lat).toBeLessThan(maxLat);
    }
  });
});
