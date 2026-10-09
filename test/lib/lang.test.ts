import { expect, it } from "vitest";
import { normalizeLang } from "../../src/lib/lang.ts";

it.each([
  ["FI", "fi"],
  ["SE", "sv"],
  ["en", "en"],
  ["Suomi", "fi"],
  [" Ruotsi ", "sv"],
  ["", undefined],
  ["Klingon", undefined],
])("normalizeLang(%s) = %s", (input, expected) => {
  expect(normalizeLang(input)).toBe(expected);
});
