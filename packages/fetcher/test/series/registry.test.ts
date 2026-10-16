import { describe, expect, it } from "vitest";
import type { ProviderBatch, Screening } from "@pgtm/model";
import { findSeries, resolveSeries, SERIES } from "../../src/series/registry.ts";

describe("the series registry", () => {
  it("loads and validates config/series.json", () => {
    expect(SERIES["kuvi-aluesarja"]).toMatchObject({ kind: "distributor-series" });
  });

  it.each([
    ["KUVIn aluesarja", "kuvi-aluesarja"],
    ["Kuvin aluesarja", "kuvi-aluesarja"],
    ["KUVI", "kuvi-aluesarja"],
    ["MATINEA", "matinea"],
    ["Tampereen elokuvajuhlat", "tampere-film-festival"],
    ["Kiirehdi", undefined],
    ["Elia Suleiman", undefined],
  ])("findSeries(%s) = %s", (name, id) => {
    expect(findSeries(name)).toBe(id);
  });
});

describe("resolveSeries", () => {
  const show = (id: string, series: string[]) => ({ id, series }) as unknown as Screening;
  const batch = {
    provider: { id: "kinoregina" },
    screenings: [
      show("a", ["Kuvin aluesarja", "KUVIn aluesarja"]),
      show("b", ["Elia Suleiman"]),
      show("c", []),
    ],
  } as unknown as ProviderBatch;

  it("turns names into registry ids, and unknown names into provider strands", () => {
    const resolved = resolveSeries(batch);
    expect(resolved.screenings.map((s) => s.series)).toEqual([
      ["kuvi-aluesarja"],
      ["kinoregina/elia-suleiman"],
      [],
    ]);
    expect(resolved.series).toEqual([
      { id: "kuvi-aluesarja", name: "KUVIn aluesarja", kind: "distributor-series" },
      { id: "kinoregina/elia-suleiman", name: "Elia Suleiman", kind: "strand" },
    ]);
  });
});
