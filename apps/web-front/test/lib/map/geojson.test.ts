import { describe, expect, it } from "vitest";
import { boundsOf, venuesToGeoJson } from "../../../src/lib/map/geojson.ts";

const venue = (over: Partial<Parameters<typeof venuesToGeoJson>[0][number]> = {}) => ({
  name: "Kino Myyri",
  city: "Vantaa",
  address: "Kinorinne 6",
  postalCode: "01600",
  geo: { lat: 60.26, lon: 24.85 },
  ...over,
});

describe("venuesToGeoJson", () => {
  it("makes a point per venue, lon first, with what the popup needs", () => {
    expect(venuesToGeoJson([venue()]).features).toEqual([
      {
        type: "Feature",
        geometry: { type: "Point", coordinates: [24.85, 60.26] },
        properties: {
          name: "Kino Myyri",
          city: "Vantaa",
          address: "Kinorinne 6, 01600 Vantaa",
          path: "/fi/elokuvateatterit/kino-myyri-vantaa",
        },
      },
    ]);
  });

  it("leaves out venues without coordinates and copes with missing addresses", () => {
    const { features } = venuesToGeoJson([
      venue({ geo: null }),
      venue({ name: "Bio Grand", address: null, postalCode: null }),
    ]);
    expect(features.map((f) => [f.properties.name, f.properties.address])).toEqual([
      ["Bio Grand", "Vantaa"],
    ]);
  });
});

describe("boundsOf", () => {
  it("frames every point, or nothing without points", () => {
    const fc = venuesToGeoJson([
      venue({ geo: { lat: 60.17, lon: 24.94 } }),
      venue({ geo: { lat: 65.01, lon: 25.47 } }),
    ]);
    expect(boundsOf(fc)).toEqual([24.94, 60.17, 25.47, 65.01]);
    expect(boundsOf(venuesToGeoJson([]))).toBeUndefined();
  });
});
