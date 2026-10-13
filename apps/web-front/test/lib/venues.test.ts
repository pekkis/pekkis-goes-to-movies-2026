import { describe, expect, it } from "vitest";
import { osmUrl, resolveVenue, venuePath, venueSlug } from "../../src/lib/venues.ts";

describe("venueSlug", () => {
  it.each([
    ["Plevna Tampere", "Tampere", "plevna-tampere"],
    ["Kino Myyri", "Vantaa", "kino-myyri-vantaa"],
    ["Studio 123", "Kouvola", "studio-123-kouvola"],
    ["Studio 123", "Järvenpää", "studio-123-jarvenpaa"],
    ["Bio Sastamala", "Sastamala", "bio-sastamala"],
    ["Kino Metso Tikkakoski", "Jyväskylä", "kino-metso-tikkakoski-jyvaskyla"],
    ["Fantasia Jyväskylä", "Jyväskylä", "fantasia-jyvaskyla"],
    // "Pori" inside "Porin…" is not the city word: the city is appended.
    ["Porin Kino", "Pori", "porin-kino-pori"],
  ])("%s (%s) -> %s", (name, city, slug) => {
    expect(venueSlug({ name, city })).toBe(slug);
  });

  it("tells same-named venues apart by city", () => {
    const venues = [
      { id: "a", name: "Maxim", city: "Varkaus" },
      { id: "b", name: "Maxim Helsinki", city: "Helsinki" },
    ];
    expect(resolveVenue("maxim-varkaus", venues)?.id).toBe("a");
    expect(resolveVenue("maxim-helsinki", venues)?.id).toBe("b");
    expect(resolveVenue("maxim", venues)).toBeUndefined();
    expect(venuePath(venues[0]!)).toBe("/fi/elokuvateatterit/maxim-varkaus");
  });

  it("links to OpenStreetMap at the venue", () => {
    expect(osmUrl({ lat: 60.27, lon: 24.85 })).toBe(
      "https://www.openstreetmap.org/?mlat=60.27&mlon=24.85#map=17/60.27/24.85",
    );
  });
});
