import { describe, expect, it } from "vitest";
import { restrictToVenues } from "../../src/providers/adapter.ts";
import { parseNexxo } from "../../src/providers/nexxo/parse.ts";
import type { NexxoRawSnapshot } from "../../src/providers/nexxo/raw.ts";
import { NEXXO_SITES, NexxoSite } from "../../src/providers/nexxo/sites.ts";
import { ADAPTERS, selectAdapters } from "../../src/providers/registry.ts";
import { defineSites } from "../../src/providers/sites.ts";
import { loadFixture } from "../fixtures.ts";

const minimal = (provider: string, slugs: string[]) => ({
  provider,
  name: "Test",
  homepage: "https://example.com",
  programmePath: "/",
  verifiedAt: "2026-10-10",
  venues: slugs.map((slug) => ({ slug, locationId: "1", name: "Kino", city: "Testilä" })),
});

describe("site configs", () => {
  it("has one adapter per Nexxo site with unique ids", () => {
    const ids = ADAPTERS.map((a) => a.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const site of NEXXO_SITES) expect(ids).toContain(site.provider);
  });

  it("rejects duplicate providers, duplicate slugs and invalid fields", () => {
    expect(() => defineSites(NexxoSite, [minimal("a", ["x"]), minimal("a", ["y"])])).toThrow(
      /Duplicate site provider/,
    );
    expect(() => defineSites(NexxoSite, [minimal("a", ["x", "x"])])).toThrow(
      /Duplicate venue slug/,
    );
    expect(() =>
      defineSites(NexxoSite, [{ ...minimal("a", ["x"]), programmePath: "naytokset" }]),
    ).toThrow();
    expect(() => defineSites(NexxoSite, [minimal("a", ["Ääne koski"])])).toThrow();
  });

  it("selects adapters by id or platform, and rejects unknown names", () => {
    expect(selectAdapters(undefined)).toBe(ADAPTERS);
    expect(selectAdapters(["nexxo"])?.map((a) => a.id)).toEqual(NEXXO_SITES.map((s) => s.provider));
    expect(selectAdapters(["biorex", "kinoaurora"])?.map((a) => a.id)).toEqual([
      "biorex",
      "kinoaurora",
    ]);
    expect(selectAdapters(["nope"])).toBeUndefined();
  });
});

describe("restrictToVenues", () => {
  const metso = NEXXO_SITES.find((s) => s.provider === "kinometso")!;
  const batch = parseNexxo(loadFixture("nexxo", "kinometso.json") as NexxoRawSnapshot, metso);

  it("keeps the selected venues and only what they reference", () => {
    const only = restrictToVenues(batch, ["tikkakoski"]);
    expect(only.venues.map((v) => v.id)).toEqual(["kinometso:venue:tikkakoski"]);
    expect(only.screenings.map((s) => s.sourceId)).toEqual(["5088"]);
    expect(only.auditoriums.map((a) => a.venueId)).toEqual(["kinometso:venue:tikkakoski"]);
    expect(only.listings.map((l) => l.sourceId)).toEqual(["901"]);
  });

  it("matches source ids too, and is a no-op without a filter", () => {
    expect(restrictToVenues(batch, ["2:petajavesi"]).venues).toHaveLength(1);
    expect(restrictToVenues(batch, undefined)).toBe(batch);
  });
});
