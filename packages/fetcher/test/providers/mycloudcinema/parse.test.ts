import { describe, expect, it } from "vitest";
import { ProviderBatch } from "@pgtm/model";
import {
  parseMyCloudCinema,
  parseRating,
  parseScreenName,
  parseSubtitles,
  parseTitleExtension,
} from "../../../src/providers/mycloudcinema/parse.ts";
import type { MyCloudCinemaRawSnapshot } from "../../../src/providers/mycloudcinema/raw.ts";
import { MYCLOUDCINEMA_SITES } from "../../../src/providers/mycloudcinema/sites.ts";
import { windows } from "../../../src/providers/mycloudcinema/fetch.ts";
import { loadFixture } from "../../fixtures.ts";

const site = (provider: string) => MYCLOUDCINEMA_SITES.find((x) => x.provider === provider)!;
const BIOREX = site("biorex");
const parseBiorex = (raw: MyCloudCinemaRawSnapshot) => parseMyCloudCinema(raw, BIOREX);

const snapshot = (overrides: Partial<MyCloudCinemaRawSnapshot> = {}): MyCloudCinemaRawSnapshot => ({
  fetchedAt: "2026-10-09T12:00:00.000Z",
  from: "2026-10-09",
  days: 7,
  cinemas: loadFixture("mycloudcinema", "biorex-cinemas.json"),
  showtimes: loadFixture("mycloudcinema", "biorex-showtimes.json") as Record<string, unknown>,
  ...overrides,
});

const screening = (batch: ProviderBatch, sourceId: string) => {
  const found = batch.screenings.find((s) => s.sourceId === sourceId);
  if (!found) {
    throw new Error(`No screening ${sourceId}`);
  }
  return found;
};

describe("MyCloudCinema: BioRex", () => {
  const batch = parseBiorex(snapshot());

  it("produces a batch that satisfies the output schema without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
  });

  it("records the business dates the fetch covered", () => {
    expect(batch.window).toEqual({ from: "2026-10-09", to: "2026-10-15" });
  });

  it("skips offline, company and closed cinemas", () => {
    expect(batch.venues.map((v) => v.sourceId)).toEqual(["1", "4", "12", "13", "14"]);
  });

  it("fills in the city the API leaves empty", () => {
    const tripla = batch.venues.find((v) => v.sourceId === "13");
    expect(tripla).toMatchObject({ name: "BioRex Tripla", city: "Helsinki" });
    expect(tripla).not.toHaveProperty("address");
  });

  it("maps a venue with address and coordinates", () => {
    expect(batch.venues[0]).toEqual({
      id: "biorex:venue:1",
      provider: "biorex",
      sourceId: "1",
      name: "BioRex Verkatehdas",
      city: "Hämeenlinna",
      address: "Paasikiventie 2",
      postalCode: "13200",
      geo: { lat: 60.99713682, lon: 24.47751687 },
    });
  });

  it("converts UTC times to Helsinki wall-clock time with offset", () => {
    expect(screening(batch, "436475")).toMatchObject({
      startsAt: "2026-10-09T15:00:00+03:00",
      businessDate: "2026-10-09",
    });
  });

  it("parses an original-language screening with Finnish and Swedish subtitles", () => {
    expect(screening(batch, "436475")).toMatchObject({
      id: "biorex:show:436475",
      venueId: "biorex:venue:1",
      auditoriumId: "biorex:screen:70",
      listingId: "biorex:film:1509",
      audio: ["en"],
      dubbed: false,
      subtitles: { kind: "languages", languages: ["fi", "sv"] },
      presentation: { projection: "digital", dimension: "2d", formats: [] },
      availability: "available",
      ticketUrl: "https://webshop.biorex.fi/fi/#/book/436475",
      unmappedLabels: [],
    });
  });

  it("parses Finnish and Swedish dubs", () => {
    expect(screening(batch, "436623")).toMatchObject({
      audio: ["fi"],
      dubbed: true,
      subtitles: { kind: "none" },
    });
    expect(screening(batch, "435890")).toMatchObject({
      audio: ["sv"],
      dubbed: true,
      subtitles: { kind: "none" },
    });
  });

  it("reads SE as Swedish", () => {
    expect(screening(batch, "436472").subtitles).toEqual({ kind: "languages", languages: ["sv"] });
  });

  it("picks Atmos from the version label", () => {
    expect(screening(batch, "436478").presentation.formats).toEqual(["atmos"]);
  });

  it("carries the K-18 limit of a licensed hall onto its screenings", () => {
    expect(screening(batch, "435836").ageLimit).toBe("K-18");
    expect(batch.auditoriums.find((a) => a.id === "biorex:screen:57")).toEqual({
      id: "biorex:screen:57",
      venueId: "biorex:venue:12",
      name: "6 REX (K-18)",
      features: [],
      ageLimit: "K-18",
    });
  });

  it("marks closed sales as not bookable and omits the ticket link", () => {
    const closed = screening(batch, "436686");
    expect(closed.availability).toBe("not-bookable");
    expect(closed).not.toHaveProperty("ticketUrl");
  });

  it("builds one listing per film with rating and genres, without vendor posters", () => {
    expect(batch.listings.find((l) => l.sourceId === "1509")).toEqual({
      id: "biorex:film:1509",
      provider: "biorex",
      sourceId: "1509",
      title: { fi: "Digger" },
      runtimeMinutes: 129,
      rating: "K-12",
      genres: ["Komedia", "Draama"],
      countries: ["Yhdysvallat"],
      kind: "film",
    });
  });

  it("sorts screenings by start time", () => {
    const times = batch.screenings.map((s) => Date.parse(s.startsAt));
    expect(times).toEqual([...times].toSorted((a, b) => a - b));
  });
});

describe("MyCloudCinema robustness", () => {
  it("turns an invalid row into a warning and keeps the rest", () => {
    const showtimes = loadFixture("mycloudcinema", "biorex-showtimes.json") as Record<
      string,
      { data: unknown[] }
    >;
    showtimes["1"]!.data.push({ show_time_id: 1, title: "Broken" });
    const batch = parseBiorex(snapshot({ showtimes }));

    expect(batch.warnings).toHaveLength(1);
    expect(batch.warnings[0]).toMatchObject({
      code: "invalid-showtime",
      context: { showTimeId: 1 },
    });
    expect(batch.screenings).toHaveLength(8);
  });

  it("warns about an unexpected response shape", () => {
    const batch = parseBiorex(snapshot({ showtimes: { "1": { error: "nope" } } }));
    expect(batch.warnings.map((w) => w.code)).toEqual(["invalid-envelope"]);
    expect(batch.screenings).toEqual([]);
  });

  it("warns about a non-zero result code", () => {
    const batch = parseBiorex(snapshot({ showtimes: { "1": { resultCode: 1, data: [] } } }));
    expect(batch.warnings.map((w) => w.code)).toEqual(["result-code"]);
  });

  it("reports unknown version flags and labels instead of dropping them", () => {
    const showtimes = loadFixture("mycloudcinema", "biorex-showtimes.json") as Record<
      string,
      { data: Record<string, unknown>[] }
    >;
    const row = showtimes["1"]!.data[0]!;
    row["version_hfr"] = 1;
    row["title_extension"] = "HFR SPECIAL";
    const batch = parseBiorex(snapshot({ showtimes: { "1": showtimes["1"] } }));

    expect(screening(batch, String(row["show_time_id"])).unmappedLabels).toEqual([
      "title_extension:HFR",
      "title_extension:SPECIAL",
      "version_hfr",
    ]);
  });
});

describe("fetch windows", () => {
  it.each([
    [7, [{ date: "2026-10-13", days: 7 }]],
    [3, [{ date: "2026-10-13", days: 3 }]],
    [
      16,
      [
        { date: "2026-10-13", days: 7 },
        { date: "2026-10-20", days: 7 },
        { date: "2026-10-27", days: 2 },
      ],
    ],
  ])("splits %d days into windows of at most 7", (days, expected) => {
    expect(windows("2026-10-13", days)).toEqual(expected);
  });

  it("asks one day at a time when the site answers only one (Cine Mäntsälä)", () => {
    expect(windows("2026-10-20", 3, 1)).toEqual([
      { date: "2026-10-20", days: 1 },
      { date: "2026-10-21", days: 1 },
      { date: "2026-10-22", days: 1 },
    ]);
  });
});

describe("field parsers", () => {
  it.each([
    ["rating_fi_s.svg", "S"],
    ["rating_fi_7.svg", "K-7"],
    ["rating_fi_12.svg", "K-12"],
    ["rating_fi_16.svg", "K-16"],
    ["rating_fi_18.svg", "K-18"],
    ["something.svg", undefined],
    [null, undefined],
  ])("parseRating(%s) = %s", (input, expected) => {
    expect(parseRating(input)).toBe(expected);
  });

  it.each([
    ["Suomi & Ruotsi -", { kind: "languages", languages: ["fi", "sv"] }],
    ["SE", { kind: "languages", languages: ["sv"] }],
    ["-", { kind: "none" }],
    ["", { kind: "unknown" }],
    [null, { kind: "unknown" }],
    ["Klingon", { kind: "unknown" }],
    ["Suomeksi ja ruotsiksi", { kind: "languages", languages: ["fi", "sv"] }],
    ["Ei", { kind: "none" }],
  ])("parseSubtitles(%s)", (input, expected) => {
    expect(parseSubtitles(input)).toEqual(expected);
  });

  it.each([
    [null, [], []],
    ["ATMOS", ["atmos"], []],
    ["FI ATMOS", ["atmos"], []],
    ["FI DUB", [], []],
    ["SWE DUB", [], []],
    ["ORIG", [], []],
    ["4DX", [], ["title_extension:4DX"]],
  ])("parseTitleExtension(%s)", (input, formats, unmapped) => {
    expect(parseTitleExtension(input)).toEqual({
      formats,
      tags: [],
      series: [],
      event: false,
      unmapped,
    });
  });

  it("reads a whole label by the shared rules (Cine Mäntsälä)", () => {
    expect(parseTitleExtension("Ennakkonäytös!")).toEqual({
      formats: [],
      tags: ["preview"],
      series: [],
      event: false,
      unmapped: [],
    });
  });

  it("reads a site's own whole label (Cine Mäntsälä's matinée strand)", () => {
    const labels = { "Cine Matinea - näytös": { series: "Cine Matinea" } };
    expect(parseTitleExtension("Cine Matinea - näytös", labels)).toEqual({
      formats: [],
      tags: [],
      series: ["Cine Matinea"],
      event: false,
      unmapped: [],
    });
  });

  it("reads Cine Mäntsälä's film-and-wine label whole: its series, the bar open (2026-10-20)", () => {
    const mantsala = MYCLOUDCINEMA_SITES.find((x) => x.provider === "cinemantsala")!;
    expect(parseTitleExtension("Leffa & viini-näytös!", mantsala.titleExtensions)).toEqual({
      formats: [],
      tags: [],
      series: ["Leffa & viini"],
      event: false,
      licensed: true,
      unmapped: [],
    });
  });

  it("reads a concert label as event cinema, with or without the exclamation mark", () => {
    const labels = {
      "Cine Konsertti": { series: "Cine Konsertti", tags: ["event-cinema" as const], event: true },
    };
    for (const raw of ["Cine Konsertti", "Cine Konsertti!"]) {
      expect(parseTitleExtension(raw, labels)).toMatchObject({
        tags: ["event-cinema"],
        series: ["Cine Konsertti"],
        event: true,
        unmapped: [],
      });
    }
  });

  it.each([
    ["Sali 3", { features: [] }],
    ["1 PRIME", { features: ["prime"] }],
    ["4 Plus", { features: ["plus"] }],
    ["6 REX (K-18)", { features: [], ageLimit: "K-18" }],
  ])("parseScreenName(%s)", (input, expected) => {
    expect(parseScreenName(input)).toEqual(expected);
  });
});

describe("MyCloudCinema: Cine Mäntsälä", () => {
  const MANTSALA = site("cinemantsala");
  const batch = parseMyCloudCinema(
    {
      fetchedAt: "2026-10-13T17:23:11.230Z",
      from: "2026-10-13",
      days: 7,
      cinemas: loadFixture("mycloudcinema", "cinemantsala-cinemas.json"),
      showtimes: loadFixture("mycloudcinema", "cinemantsala-showtimes.json") as Record<
        string,
        unknown
      >,
    },
    MANTSALA,
  );

  it("produces a valid batch without warnings, under the site's own provider", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toEqual({
      id: "cinemantsala",
      name: "Cine Mäntsälä",
      homepage: "https://mantsala.cine.fi",
      platform: "mycloudcinema",
      booking: "buy",
    });
  });

  it("reads only the configured cinema: Keuda-talo comes from eTiketti", () => {
    expect(batch.venues.map((v) => [v.id, v.name, v.city, v.address])).toEqual([
      ["cinemantsala:venue:1", "Cine Mäntsälä", "Mäntsälä", "Meijerin aukio 2"],
    ]);
    expect(batch.auditoriums.map((a) => a.name).toSorted()).toEqual(["Sali 1", "Sali 2"]);
  });

  it("links bookable shows to the cinema's own webshop, in Helsinki time", () => {
    const s = screening(batch, "13610");
    expect(s).toMatchObject({
      startsAt: "2026-10-14T13:00:00+03:00",
      businessDate: "2026-10-14",
      ticketUrl: "https://mantsala.cine.fi/#/book/13610",
      dubbed: true,
      tags: ["preview"],
      unmappedLabels: [],
    });
  });

  it.each([
    ["13613", { kind: "none" }],
    ["13602", { kind: "languages", languages: ["fi"] }],
    ["13599", { kind: "languages", languages: ["fi", "sv"] }],
    ["13598", { kind: "languages", languages: ["sv"] }],
  ])("reads the Finnish subtitle phrase of %s", (id, subtitles) => {
    expect(screening(batch, id).subtitles).toEqual(subtitles);
  });
});
