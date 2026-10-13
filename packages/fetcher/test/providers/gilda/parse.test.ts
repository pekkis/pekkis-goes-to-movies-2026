import { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import { gildaSubtitles, parseGilda } from "../../../src/providers/gilda/parse.ts";
import type { GildaRawSnapshot } from "../../../src/providers/gilda/raw.ts";
import { GILDA_SITES } from "../../../src/providers/gilda/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const SITE = GILDA_SITES[0]!;

const snapshot = (overrides: Partial<GildaRawSnapshot> = {}): GildaRawSnapshot => ({
  fetchedAt: "2026-10-13T17:28:34.946Z",
  from: "2026-10-13",
  days: 60,
  movies: loadFixture("gilda", "movies.json"),
  posts: loadFixture("gilda", "posts.json"),
  ...overrides,
});

const screening = (batch: ProviderBatch, sourceId: string) => {
  const found = batch.screenings.find((s) => s.sourceId === sourceId);
  if (!found) {
    throw new Error(`No screening ${sourceId}`);
  }
  return found;
};

describe("parseGilda", () => {
  const batch = parseGilda(snapshot(), SITE);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider.platform).toBe("mycloudcinema");
  });

  it("splits venues by screen: Gilda 1-3 in Kamppi, screen 69 is Bio Rex Lasipalatsi", () => {
    expect(screening(batch, "303546").venueId).toBe("gilda:venue:kamppi");
    const odyssey = screening(batch, "303226");
    expect(odyssey.venueId).toBe("gilda:venue:lasipalatsi");
    // "(K-18)" in the screen name is the house's door policy: a hall limit, not a rating.
    expect(odyssey.ageLimit).toBe("K-18");
    expect(batch.auditoriums.find((a) => a.id === odyssey.auditoriumId)).toMatchObject({
      name: "Bio Rex Lasipalatsi",
      ageLimit: "K-18",
    });
  });

  it("reads Helsinki time and the programme day from the UTC show time", () => {
    expect(screening(batch, "303546")).toMatchObject({
      startsAt: "2026-10-15T20:00:00+03:00",
      businessDate: "2026-10-15",
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      dubbed: false,
    });
  });

  it("strips format and series prefixes from titles, by the shared and site rules", () => {
    const titles = batch.listings.map((l) => l.title.fi);
    expect(titles).toContain("The Odyssey");
    expect(titles).toContain("Järki ja Tunteet");
    expect(screening(batch, "303226").presentation.projection).toBe("70mm");
    expect(screening(batch, "303136").tags).toEqual(["senior"]);
  });

  it("treats album listening sessions as events with no dialogue", () => {
    const album = screening(batch, "303354");
    expect(album.audio).toEqual(["zxx"]);
    expect(batch.listings.find((l) => l.id === album.listingId)?.kind).toBe("event");
  });

  it('reads "-" as no subtitles only when the style says so', () => {
    expect(screening(batch, "303234").subtitles).toEqual({ kind: "none" });
    expect(screening(batch, "303560").subtitles).toEqual({ kind: "unknown" });
    expect(gildaSubtitles("SE", "Tekstitetty")).toEqual({ kind: "languages", languages: ["sv"] });
  });

  it("skips hidden and deleted shows", () => {
    expect(batch.screenings.find((s) => s.sourceId === "303514")).toBeUndefined();
  });

  it("links to the film's own page when the site has one, else to the programme", () => {
    expect(screening(batch, "303234").ticketUrl).toBe(
      "https://www.gilda.fi/elokuva/bram-stokers-dracula/",
    );
    expect(screening(batch, "303546").ticketUrl).toBe("https://www.gilda.fi/elokuvat/");
  });

  it("carries the film's IMDb id for exact TMDB matching", () => {
    const listing = batch.listings.find((l) => l.id === screening(batch, "303546").listingId);
    expect(listing?.imdbId).toMatch(/^tt\d+$/);
  });
});

describe("parseGilda robustness", () => {
  const movies = loadFixture("gilda", "movies.json") as {
    fi: { data: { show_times: Record<string, unknown>[] }[] };
  };

  it("warns about a screen no venue owns instead of guessing", () => {
    const edited = structuredClone(movies);
    edited.fi.data[0]!.show_times[0]!["cinema_screen_id"] = 99;
    const batch = parseGilda(snapshot({ movies: edited }), SITE);
    expect(batch.warnings.map((w) => w.code)).toEqual(["unclaimed-screen"]);
  });

  it("marks a show whose sales are closed as not bookable, without a link", () => {
    const edited = structuredClone(movies);
    const show = edited.fi.data[0]!.show_times[0]!;
    show["allow_purchases"] = false;
    const batch = parseGilda(snapshot({ movies: edited }), SITE);
    const s = screening(batch, String(show["show_time_id"]));
    expect(s.availability).toBe("not-bookable");
    expect(s).not.toHaveProperty("ticketUrl");
  });

  it("keeps only shows inside the window", () => {
    const batch = parseGilda(snapshot({ days: 7 }), SITE);
    expect(batch.screenings.every((s) => s.businessDate <= "2026-10-19")).toBe(true);
    expect(batch.screenings.length).toBeGreaterThan(0);
  });
});
