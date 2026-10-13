import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { CinemahouseRawSnapshot } from "../../../src/providers/cinemahouse/fetch.ts";
import { parseCinemahouse } from "../../../src/providers/cinemahouse/parse.ts";
import { CINEMAHOUSE_SITES } from "../../../src/providers/cinemahouse/sites.ts";

const SITE = CINEMAHOUSE_SITES.find((s) => s.provider === "kinopiispanristi")!;
const HTML = readFileSync(
  join(import.meta.dirname, "../../fixtures/cinemahouse/piispanristi-etusivu.html"),
  "utf8",
);
const snapshot = (overrides: Partial<CinemahouseRawSnapshot> = {}): CinemahouseRawSnapshot => ({
  fetchedAt: "2026-10-13T17:45:00.000Z",
  from: "2026-10-13",
  days: 7,
  html: HTML,
  ...overrides,
});

describe("parseCinemahouse", () => {
  const batch = parseCinemahouse(snapshot(), SITE);
  const show = (id: string) => batch.screenings.find((s) => s.sourceId === id)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "cinema-reservations", booking: "reserve" });
    expect(batch.screenings).toHaveLength(5);
  });

  it("reads date without a year, hall, price, seats and the copied reservation link", () => {
    expect(show("3707")).toMatchObject({
      startsAt: "2026-10-14T12:00:00+03:00",
      businessDate: "2026-10-14",
      price: { amountCents: 1200, currency: "EUR" },
      availability: "available",
      ticketUrl: "https://www.kinopiispanristi.fi/varaa/?screening_id=3707",
      tags: ["preview"],
      audio: ["fi"],
      dubbed: true,
    });
    expect(batch.auditoriums.map((a) => a.name).toSorted()).toEqual([
      "Premium 5",
      "Sali 1",
      "Sali 2",
      "Sali 3",
      "Vip 4",
    ]);
  });

  it("strips capitalised labels and language markers, keeping one film per title", () => {
    expect(show("3734")).toMatchObject({ audio: ["sv"], dubbed: true });
    expect(show("3703").listingId).not.toBe(show("3734").listingId); // separate WordPress posts
    const titles = batch.listings.map((l) => l.title.fi);
    expect(titles).toContain("Pikkuli ja Tähtipeura");
    expect(titles.filter((t) => t === "Unohdettu saari")).toHaveLength(2);
  });

  it("joins film tiles for rating, runtime and genres", () => {
    const pirjo = batch.listings.find((l) => l.id === show("3716").listingId);
    expect(pirjo).toMatchObject({ rating: "S", runtimeMinutes: 88 });
    expect(pirjo?.genres.length).toBeGreaterThan(0);
  });

  it("warns when the page is not the plugin's programme", () => {
    const broken = parseCinemahouse(snapshot({ html: "<html><body>Huolto</body></html>" }), SITE);
    expect(broken.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
