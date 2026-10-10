import { describe, expect, it } from "vitest";
import {
  COMMON_TITLE_PREFIXES,
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
      },
    );
    expect(splitTitlePrefix("Ooppera: Don Giovanni", COMMON_TITLE_PREFIXES).rule?.event).toBe(true);
    expect(splitTitlePrefix("Pirjo i Sverige – Vauvakino", COMMON_TITLE_PREFIXES)).toEqual({
      title: "Pirjo i Sverige",
      rule: { tags: ["baby"] },
    });
    expect(
      splitTitlePrefix("Mission: Impossible - Dead Reckoning", COMMON_TITLE_PREFIXES).title,
    ).toBe("Mission: Impossible - Dead Reckoning");
    expect(splitTitlePrefix("Ryhmä Hau: Dinoelokuva", COMMON_TITLE_PREFIXES)).toEqual({
      title: "Ryhmä Hau: Dinoelokuva",
    });
  });
});
