import { describe, expect, it } from "vitest";
import { citiesOf, citySlug, resolveCity } from "../../src/lib/cities.ts";

describe("cities", () => {
  it.each([
    ["Jyväskylä", "jyvaskyla"],
    ["Mänttä-Vilppula", "mantta-vilppula"],
    ["Hämeenlinna", "hameenlinna"],
    [" Pori ", "pori"],
  ])("slugs %j as %j", (name, slug) => {
    expect(citySlug(name)).toBe(slug);
  });

  const venues = [
    { city: "Tampere" },
    { city: "Äänekoski" },
    { city: "Tampere" },
    { city: "Espoo" },
  ];

  it("lists each city once in Finnish order (Ä after Z)", () => {
    expect(citiesOf(venues).map((c) => c.name)).toEqual(["Espoo", "Tampere", "Äänekoski"]);
  });

  it("resolves a slug, or nothing", () => {
    expect(resolveCity("aanekoski", venues)?.name).toBe("Äänekoski");
    expect(resolveCity("nowhere", venues)).toBeUndefined();
  });
});
