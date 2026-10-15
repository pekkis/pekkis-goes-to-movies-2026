import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { AlataloRawSnapshot } from "../../../src/providers/alatalo/fetch.ts";
import { parseAlatalo } from "../../../src/providers/alatalo/parse.ts";
import { ALATALO_SITES } from "../../../src/providers/alatalo/sites.ts";

const fixture = (name: string) =>
  readFileSync(join(import.meta.dirname, "../../fixtures/alatalo", name), "utf8");
const ALATALO = ALATALO_SITES.find((s) => s.provider === "alatalo")!;
const HUVIMYLLY = ALATALO_SITES.find((s) => s.provider === "huvimylly")!;
const snapshot = (html: string): AlataloRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  html,
});
const titled = (batch: ReturnType<typeof parseAlatalo>) =>
  batch.screenings.map((s) => ({
    venue: s.venueId.split(":").at(-1),
    at: s.startsAt,
    title: batch.listings.find((l) => l.id === s.listingId)!.title.fi,
    rating: batch.listings.find((l) => l.id === s.listingId)!.rating,
  }));

describe("parseAlatalo: Movie Company Alatalo", () => {
  const html = fixture("alatalo-etusivu.html");
  const batch = parseAlatalo(snapshot(html), ALATALO);

  it("produces a valid batch, rows filed under their town", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(13);
    expect(titled(batch).filter((r) => r.venue === "kemijarvi")).toEqual([
      { venue: "kemijarvi", at: "2026-10-24T15:00:00+03:00", title: "Lapin Sota", rating: "K-16" },
      { venue: "kemijarvi", at: "2026-10-24T18:00:00+03:00", title: "Lapin Sota", rating: "K-16" },
    ]);
  });

  it("joins a title that runs onto the next line, closed by its marker", () => {
    expect(
      titled(batch).find((r) => r.venue === "haapajarvi" && r.at.endsWith("T14:00:00+03:00")),
    ).toMatchObject({
      title: "Saapasajalkakissa tekiöiltä Unohdettu saari",
      rating: "K-7",
    });
  });

  it("reads a row without Klo, and flags a rating outside the classes", () => {
    expect(
      titled(batch).some((r) => r.venue === "kiuruvesi" && r.at === "2026-10-18T16:30:00+03:00"),
    ).toBe(true);
    const k6 = batch.screenings.find((s) => s.startsAt === "2026-10-29T18:00:00+02:00")!;
    expect(k6.unmappedLabels).toEqual(["rating:6"]);
  });

  it("reads the page's one price", () => {
    expect(batch.screenings[0]?.price).toEqual({ amountCents: 1000, currency: "EUR" });
  });

  it("does not file an unknown town's rows under the town above", () => {
    const added = html.replace("<p>Kemijärvi Kulttuurikeskus</p>", "<p>Ylivieska Akustiikka</p>");
    const result = parseAlatalo(snapshot(added), ALATALO);
    expect(result.warnings.map((w) => w.code)).toEqual(["unclaimed-venue"]);
    expect(titled(result).some((r) => r.at.startsWith("2026-10-24"))).toBe(false);
  });

  it("places nothing under a weekday that fits no date", () => {
    const wrong = html.replace("Lauantaina 24.10", "Perjantaina 24.10");
    const result = parseAlatalo(snapshot(wrong), ALATALO);
    expect(result.warnings.map((w) => w.code)).toContain("invalid-row");
    expect(isIncomplete(result)).toBe(true);
  });
});

describe("parseAlatalo: Elokuvateatteri Huvimylly", () => {
  const batch = parseAlatalo(snapshot(fixture("huvimylly-etusivu.html")), HUVIMYLLY);

  it("reads a title on the line after its time, and a bare marker for the rows above it", () => {
    expect(batch.warnings).toEqual([]);
    expect(titled(batch)).toEqual([
      {
        venue: "raahe",
        at: "2026-11-01T13:00:00+02:00",
        title: "Pikkuli ja Tähtipeura",
        rating: "S",
      },
      { venue: "raahe", at: "2026-11-01T15:00:00+02:00", title: "Lapin Sota", rating: "K-16" },
      { venue: "raahe", at: "2026-11-01T18:00:00+02:00", title: "Lapin Sota", rating: "K-16" },
    ]);
  });
});
