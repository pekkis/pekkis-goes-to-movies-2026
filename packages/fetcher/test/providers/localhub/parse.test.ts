import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { LocalhubRawSnapshot } from "../../../src/providers/localhub/fetch.ts";
import { parseLocalhub } from "../../../src/providers/localhub/parse.ts";
import { LOCALHUB_SITES } from "../../../src/providers/localhub/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const SITE = LOCALHUB_SITES[0]!;
type Search = { pages: Record<string, unknown>[]; count: number };
const search = () => loadFixture("localhub", "akustiikka-search.json") as Search;
const snapshot = (overrides: Partial<LocalhubRawSnapshot> = {}): LocalhubRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  search: search(),
  ...overrides,
});

describe("parseLocalhub: Kino Akustiikka", () => {
  const batch = parseLocalhub(snapshot(), SITE);
  const listing = (key: string) => batch.listings.find((l) => l.sourceId === key)!;

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "buy" });
    expect(batch.screenings).toHaveLength(3);
  });

  it("reads the UTC start, the settled price and the shop link", () => {
    const kerro = batch.screenings.find((s) => s.listingId === listing("kerro-kaikille").id)!;
    expect(kerro).toMatchObject({
      startsAt: "2026-10-17T17:00:00+03:00",
      price: { amountCents: 1200, currency: "EUR" },
      ticketUrl: "https://verkkokauppa.ylivieska.fi/tuote/kerro-kaikille/",
    });
  });

  it("reads the rating hashtag, a year in the title and a version marker", () => {
    expect(listing("kerro-kaikille").rating).toBe("K-12");
    expect(listing("resident-evil")).toMatchObject({ title: { fi: "Resident Evil" }, year: 2026 });
    const pikkuli = batch.screenings.find(
      (s) => s.listingId === listing("pikkuli-ja-tahtipeura").id,
    )!;
    expect(pikkuli).toMatchObject({ dubbed: true, audio: ["fi"] });
  });

  it("skips a page that is not cinema, and a cancelled date", () => {
    const edited = search();
    edited.pages[0]!["globalContentCategories"] = ["Music"];
    (edited.pages[1]!["event"] as { dates: { isCancelled: boolean }[] }).dates[0]!.isCancelled =
      true;
    const result = parseLocalhub(snapshot({ search: edited }), SITE);
    expect(result.screenings).toHaveLength(1);
    expect(result.warnings).toEqual([]);
  });

  it("marks a cut answer as missing data", () => {
    const cut = { ...search(), count: 40 };
    const result = parseLocalhub(snapshot({ search: cut }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
    expect(isIncomplete(result)).toBe(true);
  });
});
