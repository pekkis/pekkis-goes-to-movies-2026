/** URL slug for a city name: "Jyväskylä" -> "jyvaskyla", "Mikkeli " -> "mikkeli". */
export const citySlug = (name: string): string =>
  name
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

export type City = { name: string; slug: string };

/** The cities venues are in, each once, in Finnish alphabetical order. */
export const citiesOf = (venues: readonly { city: string }[]): City[] =>
  [...new Set(venues.map((v) => v.city))]
    .toSorted((a, b) => a.localeCompare(b, "fi"))
    .map((name) => ({ name, slug: citySlug(name) }));

/** The city a slug names, or undefined. */
export const resolveCity = (slug: string, venues: readonly { city: string }[]) =>
  citiesOf(venues).find((c) => c.slug === slug);
