import { describe, expect, it } from "vitest";
import { collapseStarted, showStatus } from "../../src/lib/show-status.ts";

const NOW = new Date("2026-10-13T12:00:00+03:00");
const at = (time: string) => `2026-10-13T${time}:00+03:00`;

describe("showStatus", () => {
  it.each([
    [at("18:00"), "later", "", true],
    [at("13:01"), "later", "", true],
    [at("13:00"), "soon", "alkaa 60 min päästä", true],
    [at("12:01"), "soon", "alkaa nyt", true],
    [at("12:00"), "started", "alkanut", true],
    [at("11:46"), "started", "alkanut", true],
    [at("11:45"), "started", "alkanut", false],
    ["2026-10-12T20:00:00+03:00", "started", "alkanut", false], // yesterday
    ["2026-10-14T00:30:00+03:00", "later", "", true], // after midnight, tonight's programme
  ])("%s at noon: %s %j, tickets %s", (startsAt, state, label, ticketsOpen) => {
    expect(showStatus(startsAt, NOW)).toEqual({ state, label, ticketsOpen });
  });

  it("counts minutes up, so a show 30.5 min away is 31 min away", () => {
    expect(showStatus("2026-10-13T12:30:30+03:00", NOW).label).toBe("alkaa 31 min päästä");
  });
});

describe("collapseStarted", () => {
  const shows = [at("10:00"), at("19:00"), at("11:00")].map((startsAt) => ({ startsAt }));

  it("collapses started shows while others are to come", () => {
    const { collapsed, shown } = collapseStarted(shows, NOW);
    expect(collapsed.map((s) => s.startsAt)).toEqual([at("10:00"), at("11:00")]);
    expect(shown.map((s) => s.startsAt)).toEqual([at("19:00")]);
  });

  it("shows everything when nothing is left to come", () => {
    const late = new Date("2026-10-13T23:00:00+03:00");
    expect(collapseStarted(shows, late)).toEqual({ collapsed: [], shown: shows });
  });
});
