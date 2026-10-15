import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ProviderBatch, isIncomplete } from "@pgtm/model";
import { describe, expect, it } from "vitest";
import type { MyCalendarRawSnapshot } from "../../../src/providers/mycalendar/fetch.ts";
import { parseMyCalendar } from "../../../src/providers/mycalendar/parse.ts";
import { MYCALENDAR_SITES } from "../../../src/providers/mycalendar/sites.ts";
import { loadFixture } from "../../fixtures.ts";

const SITE = MYCALENDAR_SITES[0]!;
type Days = Record<string, Record<string, unknown>[]>;
const events = () => loadFixture("mycalendar", "vpk-events.json") as Days;
const INFO = readFileSync(
  join(import.meta.dirname, "../../fixtures/mycalendar/vpk-info.html"),
  "utf8",
);
const snapshot = (overrides: Partial<MyCalendarRawSnapshot> = {}): MyCalendarRawSnapshot => ({
  fetchedAt: "2026-10-15T06:00:00.000Z",
  from: "2026-10-15",
  days: 31,
  events: events(),
  info: INFO,
  ...overrides,
});

describe("parseMyCalendar: Pyhäsalmen VPK", () => {
  const batch = parseMyCalendar(snapshot(), SITE);

  it("produces a valid batch without warnings", () => {
    expect(() => ProviderBatch.parse(batch)).not.toThrow();
    expect(batch.warnings).toEqual([]);
    expect(batch.provider).toMatchObject({ platform: "custom", booking: "door" });
    expect(batch.screenings).toHaveLength(3);
  });

  it("reads the occurrence and the one price from the cinema's page", () => {
    expect(batch.screenings.find((s) => s.sourceId === "258")).toMatchObject({
      startsAt: "2026-10-23T18:00:00+03:00",
      price: { amountCents: 1200, currency: "EUR" },
      ticketUrl: SITE.info,
    });
  });

  it("publishes no price when the page did not answer", () => {
    const result = parseMyCalendar(snapshot({ info: null }), SITE);
    expect(result.screenings[0]?.price).toBeUndefined();
    expect(result.warnings).toEqual([]);
  });

  it("refuses an occurrence whose two stamps disagree", () => {
    const edited = events();
    Object.values(edited)[0]![0]!["ts_occur_begin"] = "1792771200";
    const result = parseMyCalendar(snapshot({ events: edited }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["invalid-start"]);
    expect(isIncomplete(result)).toBe(true);
  });

  it("skips, and says so, an occurrence outside the category", () => {
    const edited = events();
    Object.values(edited)[0]![0]!["category_id"] = "3";
    const result = parseMyCalendar(snapshot({ events: edited }), SITE);
    expect(result.warnings.map((w) => w.code)).toEqual(["unclaimed-event"]);
  });

  it("reads an empty answer as no screenings, and anything else as broken", () => {
    expect(parseMyCalendar(snapshot({ events: [] }), SITE).warnings).toEqual([]);
    expect(
      parseMyCalendar(snapshot({ events: { code: "rest_no_route" } }), SITE).warnings.map(
        (w) => w.code,
      ),
    ).toEqual(["invalid-response"]);
  });
});
