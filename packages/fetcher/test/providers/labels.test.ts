import { describe, expect, it } from "vitest";
import type { ProviderBatch, Screening } from "@pgtm/model";
import {
  COMMON_TITLE_PREFIXES,
  deriveTags,
  withClassicTag,
  withDomesticTag,
  findLabel,
  isPrivateBooking,
  labelEffects,
  labelKey,
  LABELS,
  splitDatedLabel,
  splitTitlePrefix,
  splitVersion,
} from "../../src/providers/labels.ts";

describe("splitVersion", () => {
  it.each([
    ["Unohdettu saari (DUB)", "Unohdettu saari", { dubbed: true, audio: "fi" }],
    ["Unohdettu saari (Dub.)", "Unohdettu saari", { dubbed: true, audio: "fi" }],
    ["Kojootti vs. ACME DUB", "Kojootti vs. ACME", { dubbed: true, audio: "fi" }],
    ["Pikkuli ja Tähtipeura (SUOMEKSI)", "Pikkuli ja Tähtipeura", { dubbed: true, audio: "fi" }],
    ["Unohdettu saari (på svenska)", "Unohdettu saari", { dubbed: true, audio: "sv" }],
    ["Kojootti vs. ACME (englanniksi)", "Kojootti vs. ACME", { dubbed: false, audio: "en" }],
    ["Unohdettu saari SUB", "Unohdettu saari", { dubbed: false }],
    ["Unohdettu saari (ORIG)", "Unohdettu saari", { dubbed: false }],
    ["Avengers: Endgame Encore 2D", "Avengers: Endgame Encore", { dimension: "2d" }],
    ["Kojootti vs. ACME, suomeksi", "Kojootti vs. ACME", { dubbed: true, audio: "fi" }],
    ["Unohdettu saari, englanniksi", "Unohdettu saari", { dubbed: false, audio: "en" }],
    ["Unohdettu saari DUP.", "Unohdettu saari", { dubbed: true, audio: "fi" }],
    ["Amadeus – ohjaajan versio", "Amadeus", {}],
    ["På svenska: Bortglömda ön", "Bortglömda ön", { dubbed: true, audio: "sv" }],
    ["Unohdettu saari SUOMEKSI", "Unohdettu saari", { dubbed: true, audio: "fi" }],
    ["Unohdettu saari PÅ SVENSKA", "Unohdettu saari", { dubbed: true, audio: "sv" }],
    // TMB writes it with or without the space.
    [
      "Pikkuli ja Tähtipeura(Puhumme suomea!)",
      "Pikkuli ja Tähtipeura",
      { dubbed: true, audio: "fi" },
    ],
  ])("%s", (raw, title, version) => {
    expect(splitVersion(raw)).toEqual({ title, version });
  });

  it("leaves other parentheses and words alone", () => {
    expect(splitVersion("The Love That Remains (Ástin sem eftir er)")).toEqual({
      title: "The Love That Remains (Ástin sem eftir er)",
      version: {},
    });
    expect(splitVersion("Hetki ennen valoa (viimeinen esitys)").version).toEqual({});
    expect(splitVersion("Sub Zero").title).toBe("Sub Zero");
    expect(splitVersion("Kerro kaikille").title).toBe("Kerro kaikille");
    expect(splitVersion("Spider-Man: Brand New Day").title).toBe("Spider-Man: Brand New Day");
    expect(splitVersion("Hyvä, paha ja ruma").title).toBe("Hyvä, paha ja ruma");
  });
});

describe("splitTitlePrefix", () => {
  it("strips only known prefixes", () => {
    expect(splitTitlePrefix("Ennakkonäytös: Pikkuli ja Tähtipeura", COMMON_TITLE_PREFIXES)).toEqual(
      {
        title: "Pikkuli ja Tähtipeura",
        rule: { tags: ["preview"] },
        label: "Ennakkonäytös",
      },
    );
    expect(splitTitlePrefix("Ooppera: Don Giovanni", COMMON_TITLE_PREFIXES).rule?.event).toBe(true);
    expect(splitTitlePrefix("Pirjo i Sverige – Vauvakino", COMMON_TITLE_PREFIXES)).toEqual({
      title: "Pirjo i Sverige",
      rule: { tags: ["baby"] },
      label: "Vauvakino",
    });
    expect(
      splitTitlePrefix("Mission: Impossible - Dead Reckoning", COMMON_TITLE_PREFIXES).title,
    ).toBe("Mission: Impossible - Dead Reckoning");
    expect(splitTitlePrefix("Ryhmä Hau: Dinoelokuva", COMMON_TITLE_PREFIXES)).toEqual({
      title: "Ryhmä Hau: Dinoelokuva",
    });
  });

  it("matches labels without regard to case (Cinemahouse writes them in capitals)", () => {
    expect(splitTitlePrefix("ENNAKKONÄYTÖS: Dyyni: Osa kolme", COMMON_TITLE_PREFIXES)).toEqual({
      title: "Dyyni: Osa kolme",
      rule: { tags: ["preview"] },
      label: "ENNAKKONÄYTÖS",
    });
    expect(splitTitlePrefix("ENNAKKO: Pikkuli", COMMON_TITLE_PREFIXES).rule).toEqual({
      tags: ["preview"],
    });
    expect(splitTitlePrefix("ENSI-ILTA: Tony", COMMON_TITLE_PREFIXES).rule).toEqual({
      tags: ["premiere"],
    });
    expect(splitVersion("Puhu suomeksi").title).toBe("Puhu suomeksi");
  });

  it("reads the same labels in parentheses at the end (TMB)", () => {
    expect(
      splitTitlePrefix(
        "Late Lammas -elokuva: Hämäräpuuhissa (Ennakkonäytös)",
        COMMON_TITLE_PREFIXES,
      ),
    ).toEqual({
      title: "Late Lammas -elokuva: Hämäräpuuhissa",
      rule: { tags: ["preview"] },
      label: "Ennakkonäytös",
    });
    expect(
      splitTitlePrefix("Pikkuli ja Tähtipeura (Ennakkonäytös!)", COMMON_TITLE_PREFIXES).title,
    ).toBe("Pikkuli ja Tähtipeura");
    expect(splitTitlePrefix("Baletti: Pähkinänsärkijä", COMMON_TITLE_PREFIXES).rule?.event).toBe(
      true,
    );
    // Unknown parentheses stay: they may be part of the title.
    expect(
      splitTitlePrefix("Madama Butterfly (Bregenz festival / Puccini)", COMMON_TITLE_PREFIXES)
        .title,
    ).toBe("Madama Butterfly (Bregenz festival / Puccini)");
  });
});

describe("series in titles", () => {
  it.each([
    [
      "Kuukauden pohjoismainen: KNYCKERTZ & SNUTJAKTEN",
      "KNYCKERTZ & SNUTJAKTEN",
      "Kuukauden pohjoismainen",
    ],
    [
      "Geel + Cézanne on Art (Taidekaupungin elokuvajuhlat)",
      "Geel + Cézanne on Art",
      "Taidekaupungin elokuvajuhlat",
    ],
    ["Muumipappa – Minikino", "Muumipappa", "Minikino"],
    ["LaatuSarja: The Testament of Ann Lee", "The Testament of Ann Lee", "LaatuSarja"],
  ])("%s", (raw, title, series) => {
    expect(splitTitlePrefix(raw, COMMON_TITLE_PREFIXES)).toEqual({
      title,
      rule: { series },
      label: series,
    });
  });

  it("leaves a prefix alone that is neither a label nor a registered series", () => {
    expect(splitTitlePrefix("Ryhmä Hau: Dinoelokuva", {}).title).toBe("Ryhmä Hau: Dinoelokuva");
  });
});

describe("the shared label table", () => {
  it.each([
    ["Ennakkonäytös!", "ennakkonäytös"],
    ["  ANNISKELUNÄYTÖS   K18 ", "anniskelunäytös k18"],
    ["(Vapaa pääsy)", "vapaa pääsy"],
  ])("labelKey(%s) = %s", (label, key) => {
    expect(labelKey(label)).toBe(key);
  });

  it.each([
    ["KIIREHDI", { availability: "few-left" }],
    ["Loppuunmyyty", { availability: "sold-out" }],
    ["Puhuttu suomeksi", { audio: "fi", dubbed: true }],
    ["Ei tekstitystä", { subtitles: "none" }],
    ["Ei puhetta", { audio: "zxx", tags: ["no-dialogue"] }],
    ["Tekijävierailu", { tags: ["guest"] }],
    ["vapaa pääsy", { tags: ["free"] }],
    ["Kuvailutulkkaus", { tags: ["audio-description"] }],
    ["35 mm", { projection: "35mm" }],
    ["Anniskelunäytös K-18", { licensed: true, ageLimit: "K-18" }],
    ["K18 - Anniskelunäytös", { licensed: true, ageLimit: "K-18" }],
    ["Oopperat ja muut eventit", { tags: ["event-cinema"], event: true }],
    ["EkaKertaLeffassa-näytös", { series: "EkaKertaLeffassa", tags: ["kids"] }],
    ["Hopeatähti-kerho", { series: "Hopeatähti", tags: ["senior"] }],
    ["Hopeatähti", { series: "Hopeatähti", tags: ["senior"] }],
  ])("%s", (label, rule) => {
    expect(findLabel(label, LABELS)).toMatchObject(rule);
  });

  it("knows nothing it was not told: strands and free text have no rule", () => {
    expect(findLabel("Matinea", LABELS)).toBeUndefined();
    expect(findLabel("Elia Suleiman", LABELS)).toBeUndefined();
  });

  it("consults site rules before the shared table", () => {
    expect(findLabel("Erikoisnäytös", { Erikoisnäytös: { tags: ["classic"] } }, LABELS)).toEqual({
      tags: ["classic"],
    });
    expect(findLabel("Erikoisnäytös", LABELS)).toEqual({});
  });

  it("merges rules: lists deduplicated, single facts from the last rule that states one", () => {
    expect(
      labelEffects([
        { tags: ["preview"], series: "Matinea" },
        undefined,
        { tags: ["preview", "kids"], availability: "few-left" },
        { availability: "sold-out", licensed: true },
      ]),
    ).toEqual({
      tags: ["preview", "kids"],
      series: ["Matinea"],
      availability: "sold-out",
      licensed: true,
    });
  });
});

describe("deriveTags", () => {
  const batchOf = (...shows: Partial<Screening>[]) =>
    ({ screenings: shows.map((s) => ({ tags: [], ...s })) }) as unknown as ProviderBatch;

  it('tags a screening with no spoken language (a silent film, "Ei puhetta") no-dialogue', () => {
    const result = deriveTags(
      batchOf({ audio: ["zxx"] }, { audio: ["zxx"], tags: ["no-dialogue"] }, { audio: ["fi"] }),
    );
    expect(result.screenings.map((s) => s.tags)).toEqual([["no-dialogue"], ["no-dialogue"], []]);
  });
});

describe("splitDatedLabel", () => {
  it.each([
    ["Lapin Sota , Ensi-ilta 23.10.", "Lapin Sota", "Ensi-ilta 23.10.", 23, 10],
    ["Pikkuli – Ennakkonäytös 3.11", "Pikkuli", "Ennakkonäytös 3.11", 3, 11],
    ["Hyvä, paha ja ruma, Ensi-ilta 1.12.", "Hyvä, paha ja ruma", "Ensi-ilta 1.12.", 1, 12],
  ])("%s", (raw, title, label, day, month) => {
    expect(splitDatedLabel(raw, LABELS)).toMatchObject({ title, label, day, month });
  });

  it("leaves titles alone that end in an unknown word and a date", () => {
    expect(splitDatedLabel("Suomi, kesä 1.9.", LABELS)).toEqual({ title: "Suomi, kesä 1.9." });
    expect(splitDatedLabel("Blade Runner 2049", LABELS)).toEqual({ title: "Blade Runner 2049" });
  });
});

describe("isPrivateBooking", () => {
  it.each([
    ["Yksityistilaisuus", true],
    [" yksityisnäytös ", true],
    ["Suljettu tilaisuus", true],
    ["Yksityinen tilaisuus", true],
    ["Yritystapahtuma", true],
    ["Tilavaraus - 6h", true],
    ["Kerro kaikille", false],
    ["Yksityisetsivä Pikkuli", false],
  ])("%s -> %s", (title, isPrivate) => {
    expect(isPrivateBooking(title)).toBe(isPrivate);
  });
});

describe("withDomesticTag", () => {
  it.each([
    [["FI"], ["domestic"]],
    [["SE", "FI"], ["domestic"]],
    [["US"], []],
    [[], []],
    [undefined, []],
  ])("a film from %o -> %o", (countries, tags) => {
    expect(withDomesticTag({ tags: [] }, countries).tags).toEqual(tags);
  });

  it("adds the tag once", () => {
    expect(withDomesticTag({ tags: ["domestic" as const] }, ["FI"]).tags).toEqual(["domestic"]);
  });
});

describe("withClassicTag", () => {
  it.each([
    [1990, ["classic"]],
    [2021, ["classic"]],
    [2022, []],
    [2026, []],
    [undefined, []],
  ])("a film from %s, shown in 2026 -> %o", (year, tags) => {
    expect(withClassicTag({ tags: [] }, year, 2026).tags).toEqual(tags);
  });

  it("keeps a cinema's own classic tag once", () => {
    expect(withClassicTag({ tags: ["classic" as const] }, 1942, 2026).tags).toEqual(["classic"]);
  });
});
