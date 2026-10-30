import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { NuorisokuvatRawSnapshot } from "../../../src/providers/nuorisokuvat/fetch.ts";
import { parseNuorisokuvat, parseShows } from "../../../src/providers/nuorisokuvat/parse.ts";
import { NUORISOKUVAT_SITES } from "../../../src/providers/nuorisokuvat/sites.ts";

const SITE = NUORISOKUVAT_SITES[0]!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/nuorisokuvat/elokuvat.html"),
  "utf8",
);
const snapshot = (overrides: Partial<NuorisokuvatRawSnapshot> = {}): NuorisokuvatRawSnapshot => ({
  fetchedAt: "2026-10-30T06:00:00.000Z",
  from: "2026-10-30",
  days: 7,
  html: HTML,
  ...overrides,
});

describe("parseShows", () => {
  it.each([
    [
      "la 31.10. klo 15 ja su 1.11 klo 18",
      [
        { weekday: "la", day: 31, month: 10, hour: 15, minute: 0 },
        { weekday: "su", day: 1, month: 11, hour: 18, minute: 0 },
      ],
    ],
    // A day without a time takes the next one's.
    [
      "ke 4.11. ja to 5.11. klo 18",
      [
        { weekday: "ke", day: 4, month: 11, hour: 18, minute: 0 },
        { weekday: "to", day: 5, month: 11, hour: 18, minute: 0 },
      ],
    ],
    ["la 31.10. klo 20.30", [{ weekday: "la", day: 31, month: 10, hour: 20, minute: 30 }]],
    ["la 31.10.", undefined],
    ["lauantaina", undefined],
  ])("%s", (text, shows) => {
    expect(parseShows(text)).toEqual(shows);
  });
});

describe("parseNuorisokuvat", () => {
  const batch = parseNuorisokuvat(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;
  const listing = (title: string) => batch.listings.find((l) => l.title.fi === title)!;

  it("produces a valid batch; a film without shows is not listed", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(5);
    expect(batch.listings.map((l) => l.title.fi)).not.toContain("Kerro Kaikille");
  });

  it("reads the facts: runtime, age limit, price and the ticket link", () => {
    expect(listing("Lapin Sota")).toMatchObject({ runtimeMinutes: 158, rating: "K-16" });
    expect(show("lapin-sota-202611041800")).toMatchObject({
      startsAt: "2026-11-04T18:00:00+02:00",
      price: { amountCents: 1200, currency: "EUR" },
      ticketUrl: "https://vimpelinveto.fi/elokuvat/osta-liput",
    });
  });

  it("tags a free show and publishes no price for it", () => {
    const free = show("other-mommy-202610312000");
    expect(free.tags).toEqual(["free"]);
    expect(free.price).toBeUndefined();
  });

  it("warns about shows it cannot read", () => {
    const broken = HTML.replace("la 31.10. klo 20", "lauantaina illalla");
    const result = parseNuorisokuvat(snapshot({ html: broken }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
