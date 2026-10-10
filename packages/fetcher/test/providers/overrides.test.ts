import { describe, expect, it } from "vitest";
import type { ProviderBatch, Venue } from "@pgtm/model";
import { finishVenues, loadVenueOverrides, VenueOverrides } from "../../src/providers/overrides.ts";

const venue = (id: string, extra: Partial<Venue> = {}): Venue => ({
  id: `testchain:venue:${id}`,
  provider: "testchain",
  sourceId: id,
  name: `Kino ${id}`,
  city: "Pori",
  ...extra,
});

const batch = (venues: Venue[]): ProviderBatch => ({
  provider: {
    id: "testchain",
    name: "Test",
    homepage: "https://example.com",
    platform: "custom",
    booking: "buy",
  },
  fetchedAt: "2026-10-10T07:00:00.000Z",
  window: { from: "2026-10-10", to: "2026-10-16" },
  venues,
  auditoriums: [],
  listings: [],
  screenings: [],
  warnings: [],
});

describe("finishVenues", () => {
  it("applies overrides over provider data", () => {
    const out = finishVenues(batch([venue("1", { geo: { lat: 61.5, lon: 21.7 } })]), {
      "testchain:venue:1": {
        name: "Kino 1",
        geo: { lat: 61.48, lon: 21.79 },
        geoSource: "osm:node/1",
        address: "Yrjönkatu 17",
        note: "wrong point upstream",
      },
    });
    expect(out.venues[0]).toMatchObject({
      geo: { lat: 61.48, lon: 21.79 },
      address: "Yrjönkatu 17",
    });
    expect(out.warnings).toEqual([]);
  });

  it("warns once per venue still without coordinates", () => {
    const out = finishVenues(
      batch([venue("1"), venue("2", { geo: { lat: 61.5, lon: 21.7 } })]),
      {},
    );
    expect(out.warnings).toEqual([
      expect.objectContaining({
        code: "venue-without-geo",
        context: { venueId: "testchain:venue:1" },
      }),
    ]);
  });
});

describe("VenueOverrides", () => {
  it("requires a source with geo", () => {
    expect(
      VenueOverrides.safeParse({ "a:venue:1": { name: "X", geo: { lat: 61, lon: 25 }, note: "n" } })
        .success,
    ).toBe(false);
  });

  it("the committed config file is valid", async () => {
    await expect(loadVenueOverrides()).resolves.toBeDefined();
  });
});
