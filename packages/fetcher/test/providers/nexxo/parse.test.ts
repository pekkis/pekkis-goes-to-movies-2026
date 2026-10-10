import { describe, expect, it } from "vitest";
import { ProviderBatch } from "@pgtm/model";
import {
  parseAge,
  parseAudio,
  parseNexxo,
  parseSubtitles,
  splitTitlePrefix,
  toIso,
} from "../../../src/providers/nexxo/parse.ts";
import type { NexxoRawSnapshot } from "../../../src/providers/nexxo/raw.ts";
import { NEXXO_SITES, type NexxoSite } from "../../../src/providers/nexxo/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const site = (provider: string): NexxoSite => {
  const found = NEXXO_SITES.find((s) => s.provider === provider);
  if (!found) throw new Error(`No site ${provider}`);
  return found;
};

const snapshot = (name: string, overrides: Partial<NexxoRawSnapshot> = {}): NexxoRawSnapshot => ({
  ...(loadFixture("nexxo", `${name}.json`) as NexxoRawSnapshot),
  ...overrides,
});

const screening = (batch: ProviderBatch, sourceId: string) => {
  const found = batch.screenings.find((s) => s.sourceId === sourceId);
  if (!found) throw new Error(`No screening ${sourceId}`);
  return found;
};

describe("Nexxo field parsers", () => {
  it("reads audio codes, skipping OV and mapping SE and IW", () => {
    expect(parseAudio("FI")).toEqual({ audio: ["fi"], unknown: [] });
    expect(parseAudio("SE")).toEqual({ audio: ["sv"], unknown: [] });
    expect(parseAudio("IW")).toEqual({ audio: ["he"], unknown: [] });
    expect(parseAudio("OV")).toEqual({ audio: [], unknown: [] });
    expect(parseAudio("XYZ")).toEqual({ audio: [], unknown: ["XYZ"] });
    expect(parseAudio(null)).toEqual({ audio: [], unknown: [] });
  });

  it("reads subtitle codes", () => {
    expect(parseSubtitles("FI-SE")).toEqual({ kind: "languages", languages: ["fi", "sv"] });
    expect(parseSubtitles("XX")).toEqual({ kind: "none" });
    expect(parseSubtitles("OV")).toEqual({ kind: "unknown" });
    expect(parseSubtitles("")).toEqual({ kind: "unknown" });
    expect(parseSubtitles("FI-XYZ")).toEqual({ kind: "unknown" });
  });

  it("reads ratings, and event age limits as screening limits", () => {
    expect(parseAge("12")).toEqual({ rating: "K-12" });
    expect(parseAge("s")).toEqual({ rating: "S" });
    expect(parseAge("K16")).toEqual({ rating: "K-16" });
    expect(parseAge("Tapahtuma K18")).toEqual({ ageLimit: "K-18" });
    expect(parseAge("")).toEqual({});
    expect(parseAge("joku")).toEqual({});
  });

  it("converts Helsinki local time across the DST change", () => {
    expect(toIso("2026-10-10 15:00:00")).toBe("2026-10-10T15:00:00+03:00");
    expect(toIso("2026-10-26 18:00")).toBe("2026-10-26T18:00:00+02:00");
    expect(toIso("10.10.2026 15:00")).toBeUndefined();
  });

  it("strips only configured title prefixes", () => {
    const aurora = site("kinoaurora");
    expect(splitTitlePrefix(aurora, "Ennakkoensi-ilta: Pikkuli ja Tähtipeura")).toEqual({
      title: "Pikkuli ja Tähtipeura",
      rule: { tags: ["preview"] },
    });
    expect(splitTitlePrefix(aurora, "Rauhanviikko: Naza").title).toBe("Naza");
    expect(splitTitlePrefix(aurora, "Ryhmä Hau: Dinoelokuva")).toEqual({
      title: "Ryhmä Hau: Dinoelokuva",
    });
    // Site rules do not leak to other sites; defaults apply everywhere.
    expect(splitTitlePrefix(site("kinoset"), "Rauhanviikko: Naza").title).toBe(
      "Rauhanviikko: Naza",
    );
    expect(splitTitlePrefix(site("kinoset"), "Ennakkoensi-ilta: X").title).toBe("X");
  });
});

describe("parseNexxo", () => {
  it.each(["kinomarilyn", "kinoaurora", "kinometso", "biosade"])(
    "%s: produces a valid batch without warnings",
    (name) => {
      const batch = parseNexxo(snapshot(name), site(name));
      expect(() => ProviderBatch.parse(batch)).not.toThrow();
      expect(batch.warnings).toEqual([]);
      expect(batch.screenings.length).toBeGreaterThan(0);
      expect(batch.provider).toMatchObject({ id: name, platform: "nexxo", booking: "reserve" });
    },
  );

  it("takes venue address and coordinates from the config", () => {
    const batch = parseNexxo(snapshot("kinomarilyn"), site("kinomarilyn"));
    expect(batch.venues[0]).toMatchObject({
      address: "Kuningattarenkatu 17",
      postalCode: "07900",
      geo: { lat: 60.458467, lon: 26.225406 },
    });
  });

  it("maps a regular screening", () => {
    const batch = parseNexxo(snapshot("kinomarilyn"), site("kinomarilyn"));
    expect(screening(batch, "3046")).toMatchObject({
      id: "kinomarilyn:show:3046",
      venueId: "kinomarilyn:venue:loviisa",
      auditoriumId: "kinomarilyn:screen:1-1",
      listingId: "kinomarilyn:film:563",
      startsAt: "2026-10-10T12:30:00+03:00",
      businessDate: "2026-10-10",
      presentation: { projection: "digital", dimension: "2d", formats: [] },
      audio: ["sv"],
      subtitles: { kind: "none" },
      availability: "unknown",
      price: { amountCents: 1100, currency: "EUR" },
      ticketUrl: "https://kinomarilyn.fi/esitysajat/?location=1",
      unmappedLabels: [],
    });
    expect(batch.listings.find((l) => l.sourceId === "563")).toMatchObject({
      runtimeMinutes: 109,
      rating: "K-7",
      genres: ["Komedia", "Seikkailu", "Perhe-elokuva", "Animaatio", "Fantasia"],
      kind: "film",
    });
  });

  it("applies show type rules: events, ignored labels, and series for unknown ones", () => {
    const batch = parseNexxo(snapshot("kinomarilyn"), site("kinomarilyn"));
    expect(screening(batch, "2210").tags).toEqual(["event-cinema"]);
    expect(batch.listings.find((l) => l.sourceId === "431")?.kind).toBe("event");
    expect(screening(batch, "2813").series).toEqual(["Aikuisten leffakerho"]);
    expect(screening(batch, "3046").series).toEqual([]);
  });

  it("treats a 'Tapahtuma K18' age limit as an event with a screening age limit", () => {
    const batch = parseNexxo(snapshot("kinomarilyn"), site("kinomarilyn"));
    expect(screening(batch, "2851")).toMatchObject({ ageLimit: "K-18", series: ["Leijonat"] });
    const listing = batch.listings.find((l) => l.sourceId === "537");
    expect(listing).toMatchObject({ kind: "event" });
    expect(listing?.rating).toBeUndefined();
  });

  it("strips title prefixes into tags and series", () => {
    const batch = parseNexxo(snapshot("kinoaurora"), site("kinoaurora"));
    expect(batch.listings.find((l) => l.sourceId === "1136")?.title.fi).toBe(
      "Late Lammas -elokuva: Hämäräpuuhissa",
    );
    expect(screening(batch, "5241").tags).toEqual(["preview"]);
    expect(screening(batch, "5264")).toMatchObject({
      series: ["Rauhanviikko"],
      audio: ["he"],
      subtitles: { kind: "languages", languages: ["en"] },
    });
    // A range is not a year.
    expect(batch.listings.find((l) => l.sourceId === "1149")?.year).toBe(1974);
  });

  it("splits a shared location into venues by room, with per-venue pages", () => {
    const batch = parseNexxo(snapshot("kinometso"), site("kinometso"));
    expect(batch.venues.map((v) => v.id)).toEqual([
      "kinometso:venue:muurame",
      "kinometso:venue:petajavesi",
      "kinometso:venue:tikkakoski",
      "kinometso:venue:vaajakoski",
      "kinometso:venue:laukaa",
      "kinometso:venue:viitasaari",
    ]);
    expect(screening(batch, "5187")).toMatchObject({
      venueId: "kinometso:venue:petajavesi",
      ticketUrl: "https://ksek.fi/kino-metso/petajavesi/",
      series: [],
    });
    expect(screening(batch, "5088")).toMatchObject({
      venueId: "kinometso:venue:tikkakoski",
      series: ["Minikino"],
      tags: ["kids"],
    });
    // Price 0.00 means not set.
    expect(screening(batch, "5088").price).toBeUndefined();
  });

  it("warns about rooms no venue claims instead of guessing", () => {
    const metso = site("kinometso");
    const batch = parseNexxo(snapshot("kinometso"), {
      ...metso,
      venues: metso.venues.filter((v) => v.slug !== "tikkakoski"),
    });
    expect(batch.screenings.some((s) => s.sourceId === "5088")).toBe(false);
    // One warning per room, not per show.
    expect(batch.warnings).toEqual([
      expect.objectContaining({
        code: "unclaimed-room",
        context: expect.objectContaining({ roomId: "11", shows: 1 }),
      }),
    ]);
  });

  it("links to the homepage even when the data comes from another host", () => {
    const batch = parseNexxo(snapshot("biosade"), site("biosade"));
    expect(batch.screenings[0]?.ticketUrl).toBe("https://www.biosade.fi/?location=4");
    expect(screening(batch, "994294704").subtitles).toEqual({ kind: "unknown" });
  });

  it("keeps only screenings inside the requested window", () => {
    const batch = parseNexxo(snapshot("kinomarilyn", { days: 2 }), site("kinomarilyn"));
    expect(batch.window).toEqual({ from: "2026-10-10", to: "2026-10-11" });
    expect(batch.screenings.map((s) => s.businessDate)).toEqual([
      "2026-10-10",
      "2026-10-10",
      "2026-10-11",
    ]);
  });

  it("reads an empty programme ([]) as no screenings", () => {
    const batch = parseNexxo(snapshot("empty"), site("kinoaurora"));
    expect(batch.screenings).toEqual([]);
    expect(batch.warnings).toEqual([]);
    expect(batch.venues).toHaveLength(1);
  });

  it("turns broken payloads and rows into warnings", () => {
    const batch = parseNexxo(
      snapshot("empty", {
        payloads: {
          "1": {
            shows: {
              "2026-10-10": [
                { showId: "1" },
                { showId: "2", movieId: "3", movieTitle: "X", startTime: "huomenna" },
              ],
            },
          },
        },
      }),
      site("kinoaurora"),
    );
    expect(batch.warnings.map((w) => w.code)).toEqual(["invalid-show", "invalid-start"]);

    const broken = parseNexxo(
      snapshot("empty", { payloads: { "1": "<html>" } }),
      site("kinoaurora"),
    );
    expect(broken.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
