import { describe, expect, it } from "vitest";
import {
  candidatesFor,
  geoSnippet,
  nameSimilarity,
  suspiciousCoordinates,
} from "../../src/geo/match.ts";
import { parseNominatim } from "../../src/geo/nominatim.ts";
import { parseOverpass } from "../../src/geo/osm.ts";
import { loadFixture } from "../fixtures.ts";

const cinemas = parseOverpass(loadFixture("osm", "overpass.json"));
const byRef = (ref: string) => cinemas.find((c) => c.ref === ref)!;

describe("parseOverpass", () => {
  it("reads nodes and ways (via their centre) with address tags", () => {
    expect(cinemas).toHaveLength(5);
    expect(byRef("osm:node/514273201")).toEqual({
      ref: "osm:node/514273201",
      url: "https://www.openstreetmap.org/node/514273201",
      name: "Promenadi",
      lat: 61.4839071,
      lon: 21.7965773,
      city: "Pori",
      address: "Yrjönkatu 17",
      postalCode: "28100",
    });
    expect(byRef("osm:way/148579739")).toMatchObject({ name: "Järvelän Kino" });
  });

  it("skips elements without a position", () => {
    expect(parseOverpass({ elements: [{ type: "relation", id: 1, tags: { name: "X" } }] })).toEqual(
      [],
    );
  });
});

describe("candidatesFor", () => {
  it("puts the matching name first, ahead of a same-city cinema", () => {
    const [first, ...rest] = candidatesFor(
      { id: "kinomarilyn:venue:loviisa", name: "Kino Marilyn", city: "Loviisa" },
      cinemas,
    );
    expect(first?.cinema.ref).toBe("osm:node/2104773059");
    expect(first?.sameCity).toBe(true);
    // Bio Marilyn (Lapua) is a similar name, so it is offered, but below.
    expect(rest.map((c) => c.cinema.name)).toContain("Bio Marilyn");
  });

  it("does not let a same-city bonus beat a clearly matching name", () => {
    const [first] = candidatesFor(
      { id: "x:venue:1", name: "Järvelän Kino", city: "Jyväskylä" },
      cinemas,
    );
    expect(first?.cinema.name).toBe("Järvelän Kino");
  });

  it("returns nothing when no name or city is close", () => {
    expect(
      candidatesFor({ id: "x:venue:1", name: "Kino Metso Muurame", city: "Muurame" }, cinemas),
    ).toEqual([]);
  });
});

describe("suspiciousCoordinates", () => {
  it("flags venues far from every OSM cinema (Finnkino's own point for Promenadi)", () => {
    const pori = { id: "finnkino:venue:1004", name: "Promenadi Pori", city: "Pori" };
    const [suspect] = suspiciousCoordinates(
      [{ ...pori, geo: { lat: 61.51614827, lon: 21.77650159 } }],
      cinemas,
    );
    expect(suspect?.nearest?.ref).toBe("osm:node/514273201");
    expect(suspect?.distance).toBeGreaterThan(3_000);

    expect(
      suspiciousCoordinates([{ ...pori, geo: { lat: 61.483907, lon: 21.796577 } }], cinemas),
    ).toEqual([]);
  });

  it("ignores venues without coordinates", () => {
    expect(suspiciousCoordinates([{ id: "x:venue:1", name: "X", city: "Y" }], cinemas)).toEqual([]);
  });
});

describe("snippets and geocoding", () => {
  it("prints a pasteable snippet with at most six decimals", () => {
    expect(geoSnippet({ lat: 61.4839071, lon: 21.7965773 }, "osm:node/514273201")).toBe(
      'geo: { lat: 61.483907, lon: 21.796577 }, geoSource: "osm:node/514273201",',
    );
  });

  it("parses Nominatim results", () => {
    expect(
      parseNominatim([
        {
          osm_type: "way",
          osm_id: 865724599,
          lat: "62.2496700",
          lon: "25.8735220",
          display_name: "Vaajakosken urheilutalo, 9, Savonmäentie, Vaajakoski, Jyväskylä",
        },
      ]),
    ).toEqual([
      {
        lat: 62.24967,
        lon: 25.873522,
        label: "Vaajakosken urheilutalo, 9, Savonmäentie, Vaajakoski, Jyväskylä",
        url: "https://www.openstreetmap.org/way/865724599",
      },
    ]);
    expect(parseNominatim([])).toEqual([]);
  });

  it("scores names like pg_trgm", () => {
    expect(nameSimilarity("Kino Marilyn", "Kino Marilyn")).toBe(1);
    expect(nameSimilarity("Kino Marilyn", "Fantasia")).toBe(0);
  });
});
