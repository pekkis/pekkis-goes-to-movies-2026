import { expect, it } from "vitest";
import { toCountryCodes } from "../../src/matching/countries.ts";
import { normalizeTitle, stripQualifiers, titlePrefix } from "../../src/matching/titles.ts";

it.each([
  ["Kätyrit & Monsterit", "kätyrit and monsterit"],
  ["Spider-Man: Brand New Day", "spider man brand new day"],
  ["  Coyote vs. Acme ", "coyote vs acme"],
])("normalizeTitle(%s)", (input, expected) => {
  expect(normalizeTitle(input)).toBe(expected);
});

it.each([
  ["Practical Magic: Lumotut sisaret", "Practical Magic"],
  ["Late Lammas -elokuva: Hämäräpuuhissa", "Late Lammas"],
  ["Ryhmä Hau: Dinoelokuva", "Ryhmä Hau"],
  ["Mission – Final", "Mission"],
  ["Digger", undefined],
  ["Up: Ylös", undefined],
])("titlePrefix(%s)", (input, expected) => {
  expect(titlePrefix(input)).toBe(expected);
});

it("maps Finnish country names and drops unknown ones", () => {
  expect(toCountryCodes(["Yhdysvallat", "Tsekin Tasavalta", "Atlantis", "yhdysvallat"])).toEqual([
    "US",
    "CZ",
  ]);
});

it.each([
  ["Nalle Puhin elokuva (dub)", "Nalle Puhin elokuva"],
  ["Vaiana (liveaction)", "Vaiana"],
  ["Autot (uudelleenjulkaisu) (orig)", "Autot"],
  ["(500) Days of Summer", "(500) Days of Summer"],
  ["(dub)", "(dub)"],
])("stripQualifiers(%s)", (input, expected) => {
  expect(stripQualifiers(input)).toBe(expected);
});
