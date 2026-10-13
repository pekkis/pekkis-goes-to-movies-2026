import type { StyleSpecification } from "maplibre-gl";
import { describe, expect, it } from "vitest";
import { localizeLabels } from "../../../src/lib/map/labels.ts";

const style = {
  version: 8,
  sources: {},
  layers: [
    { id: "bg", type: "background" },
    {
      id: "place",
      type: "symbol",
      source: "openmaptiles",
      layout: { "text-field": ["coalesce", ["get", "name_en"], ["get", "name"]] },
    },
    {
      id: "road-number",
      type: "symbol",
      source: "openmaptiles",
      layout: { "text-field": ["to-string", ["get", "ref"]] },
    },
  ],
} as StyleSpecification;

describe("localizeLabels", () => {
  it("prefers the language's names on place labels, leaving other labels alone", () => {
    const [bg, place, road] = localizeLabels(style, "fi").layers;
    expect(bg).toEqual(style.layers[0]);
    expect(place?.type === "symbol" && place.layout?.["text-field"]).toEqual([
      "coalesce",
      ["get", "name:fi"],
      ["get", "name:latin"],
      ["get", "name"],
    ]);
    expect(road).toEqual(style.layers[2]);
  });
});
