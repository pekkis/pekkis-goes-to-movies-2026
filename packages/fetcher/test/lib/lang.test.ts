import { describe, expect, it } from "vitest";
import { normalizeLang, normalizeLangs } from "../../src/lib/lang.ts";

it.each([
  ["FI", "fi"],
  ["SE", "sv"],
  ["en", "en"],
  ["Suomi", "fi"],
  [" Ruotsi ", "sv"],
  ["pashtu", "ps"],
  ["pushto", "ps"],
  ["kannada", "kn"],
  ["mykkä elokuva", "zxx"],
  ["dari", "fa"],
  ["", undefined],
  ["Klingon", undefined],
  // Country codes for languages; a two-letter code that is no language is unknown.
  ["JP", "ja"],
  ["DK", "da"],
  ["IW", "he"],
  ["xx", undefined],
  ["ov", undefined],
])("normalizeLang(%s) = %s", (input, expected) => {
  expect(normalizeLang(input)).toBe(expected);
});

describe("lookup tables", () => {
  it("do not match inherited object properties", () => {
    expect(normalizeLang("constructor")).toBeUndefined();
    expect(normalizeLang("toString")).toBeUndefined();
    expect(normalizeLang("__proto__")).toBeUndefined();
  });
});

describe("normalizeLangs", () => {
  it.each([
    ["EN & FI", ["en", "fi"]],
    ["fi", ["fi"]],
    ["englanti, suomi", ["en", "fi"]],
    ["suomi ja ruotsi", ["fi", "sv"]],
    ["English and Finnish", ["en", "fi"]],
    ["EN & EN", ["en"]],
    ["EN & Klingon", undefined],
    ["FI/SV", undefined],
    ["", undefined],
  ])("%j -> %j", (input, expected) => {
    expect(normalizeLangs(input)).toEqual(expected);
  });
});
