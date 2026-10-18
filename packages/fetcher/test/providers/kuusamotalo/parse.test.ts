import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { KuusamotaloRawSnapshot } from "../../../src/providers/kuusamotalo/fetch.ts";
import { parseKuusamotalo } from "../../../src/providers/kuusamotalo/parse.ts";
import { KUUSAMOTALO_SITES } from "../../../src/providers/kuusamotalo/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const SITE = KUUSAMOTALO_SITES[0]!;
type Post = {
  id: number;
  link: string;
  title: { rendered: string };
  content: { rendered: string };
};
const posts = () => loadFixture("kuusamotalo", "kuusamotalo-posts.json") as Post[];
const snapshot = (overrides: Partial<KuusamotaloRawSnapshot> = {}): KuusamotaloRawSnapshot => ({
  fetchedAt: "2026-10-14T06:00:00.000Z",
  from: "2026-10-14",
  days: 31,
  posts: posts(),
  ...overrides,
});

describe("parseKuusamotalo", () => {
  const batch = parseKuusamotalo(snapshot(), SITE);

  it("produces a valid batch from the film posts only", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.listings.map((l) => l.title.fi)).toEqual(["Pirjo i Sverige"]);
  });

  it("splits a row with several times into screenings", () => {
    expect(batch.screenings.map((s) => s.startsAt).slice(0, 2)).toEqual([
      "2026-10-14T15:00:00+03:00",
      "2026-10-14T19:00:00+03:00",
    ]);
    expect(batch.screenings).toHaveLength(9);
  });

  it("reads a note after the times; the last screening is the day's last time (2026-10-18)", () => {
    const noted = posts().map((p) => ({
      ...p,
      content: {
        rendered: p.content.rendered.replace(
          "Ke 21.10. klo 15 ja 19<",
          "Ke 21.10. klo 15 ja 19 ( viimeinen näytös )<",
        ),
      },
    }));
    const result = parseKuusamotalo(snapshot({ posts: noted }), SITE);
    expect(result.warnings).toEqual([]);
    const day = result.screenings.filter((s) => s.businessDate === "2026-10-21");
    expect(day.map((s) => s.tags)).toEqual([[], ["last-screening"]]);
    expect(day[1]?.labels).toEqual([{ source: "row.note", text: "viimeinen näytös" }]);

    const unknown = posts().map((p) => ({
      ...p,
      content: {
        rendered: p.content.rendered.replace(
          "Ke 21.10. klo 15 ja 19<",
          "Ke 21.10. klo 15 ja 19 (kahvit)<",
        ),
      },
    }));
    const other = parseKuusamotalo(snapshot({ posts: unknown }), SITE);
    expect(other.screenings.find((s) => s.businessDate === "2026-10-21")?.unmappedLabels).toEqual([
      "note:kahvit",
    ]);
  });

  it("reads the facts before the list", () => {
    expect(batch.listings[0]).toMatchObject({ rating: "S", runtimeMinutes: 88 });
    expect(batch.screenings[0]).toMatchObject({
      price: { amountCents: 1200, currency: "EUR" },
      ticketUrl: "https://kinokuusamotalo.fi/2026/09/30/pirjo-i-sverige/",
    });
  });

  it("places nothing when the weekday does not fit the date", () => {
    const edited = posts();
    edited[0]!.content.rendered = edited[0]!.content.rendered.replace("Pe 16.10.", "To 16.10.");
    const result = parseKuusamotalo(snapshot({ posts: edited }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-row"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("warns when the answer is not a list of posts", () => {
    const result = parseKuusamotalo(snapshot({ posts: { code: "rest_no_route" } }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-response"]);
  });
});
