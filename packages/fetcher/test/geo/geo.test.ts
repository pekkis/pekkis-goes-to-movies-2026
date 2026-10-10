import { describe, expect, it } from "vitest";
import { distanceMeters, FinnishGeo, GeoSource } from "../../src/geo/geo.ts";

describe("FinnishGeo", () => {
  it("accepts points in Finland, Åland and Lapland", () => {
    expect(FinnishGeo.safeParse({ lat: 60.17, lon: 24.94 }).success).toBe(true);
    expect(FinnishGeo.safeParse({ lat: 60.1, lon: 19.94 }).success).toBe(true);
    expect(FinnishGeo.safeParse({ lat: 69.9, lon: 27.0 }).success).toBe(true);
  });

  it("rejects swapped coordinates and points abroad", () => {
    expect(FinnishGeo.safeParse({ lat: 24.94, lon: 60.17 }).success).toBe(false);
    expect(FinnishGeo.safeParse({ lat: 59.33, lon: 18.07 }).success).toBe(false); // Stockholm
  });
});

describe("GeoSource", () => {
  it("takes OSM refs and the known geocoders", () => {
    for (const source of ["osm:node/1", "osm:way/148579739", "nominatim", "nls", "manual"]) {
      expect(GeoSource.safeParse(source).success).toBe(true);
    }
  });

  it("rejects anything else", () => {
    for (const source of ["google", "osm:node/", "osm:area/1", ""]) {
      expect(GeoSource.safeParse(source).success).toBe(false);
    }
  });
});

describe("distanceMeters", () => {
  it("measures great-circle distance", () => {
    expect(distanceMeters({ lat: 60.17, lon: 24.94 }, { lat: 60.17, lon: 24.94 })).toBe(0);
    // Helsinki - Tampere is about 160 km.
    const d = distanceMeters({ lat: 60.1699, lon: 24.9384 }, { lat: 61.4978, lon: 23.761 });
    expect(d).toBeGreaterThan(155_000);
    expect(d).toBeLessThan(165_000);
  });
});
