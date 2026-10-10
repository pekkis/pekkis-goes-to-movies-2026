import { describe, expect, it } from "vitest";
import { parseCoreLocation, parseIpinfo, parseNominatim } from "../src/geo/locate.ts";

describe("parseCoreLocation", () => {
  it("reads CoreLocationCLI --json output", () => {
    expect(
      parseCoreLocation(
        JSON.stringify({
          latitude: 62.2366,
          longitude: 25.735,
          h_accuracy: 35.2,
          locality: "Jyväskylä",
        }),
      ),
    ).toEqual({
      lat: 62.2366,
      lon: 25.735,
      label: "this Mac (CoreLocation, ±35 m)",
      approximate: false,
    });
  });

  it("rejects errors and empty fixes", () => {
    expect(parseCoreLocation("kCLErrorDomain error 0")).toBeUndefined();
    expect(parseCoreLocation(JSON.stringify({ latitude: 0, longitude: 0 }))).toBeUndefined();
  });
});

describe("parseIpinfo", () => {
  it("reads loc and names the place, marked approximate", () => {
    expect(
      parseIpinfo({ ip: "192.0.2.1", city: "Myyrmäki", region: "Uusimaa", loc: "60.2671,24.8471" }),
    ).toEqual({
      lat: 60.2671,
      lon: 24.8471,
      label: "your IP address (ipinfo.io: Myyrmäki, Uusimaa)",
      approximate: true,
    });
  });

  it("rejects answers without a position (e.g. a bogon address)", () => {
    expect(parseIpinfo({ ip: "10.0.0.1", bogon: true })).toBeUndefined();
    expect(parseIpinfo("nope")).toBeUndefined();
  });
});

describe("parseNominatim", () => {
  it("takes the best match and shortens its name", () => {
    expect(
      parseNominatim([
        {
          lat: "62.2366190",
          lon: "25.7350020",
          display_name:
            "Kulttuurikeskus Villa Rana, 13, Seminaarinkatu, Mattilanniemi, Jyväskylä, Keski-Suomi, 40100, Suomi / Finland",
        },
      ]),
    ).toEqual({
      lat: 62.236619,
      lon: 25.735002,
      label:
        "Kulttuurikeskus Villa Rana, 13, Seminaarinkatu, Mattilanniemi (© OpenStreetMap contributors)",
      approximate: false,
    });
  });

  it("returns nothing when nothing was found", () => {
    expect(parseNominatim([])).toBeUndefined();
  });
});
