import { describe, expect, it } from "vitest";
import { normalizeLang } from "../../src/lib/lang.ts";

it.each([
  ["FI", "fi"],
  ["SE", "sv"],
  ["en", "en"],
  ["Suomi", "fi"],
  [" Ruotsi ", "sv"],
  ["pashtu", "ps"],
  ["dari", "fa"],
  ["", undefined],
  ["Klingon", undefined],
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
