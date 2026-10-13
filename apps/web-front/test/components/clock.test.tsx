// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ClockIsland, useNow, useShowStatus } from "../../src/components/clock.tsx";
import { advanceMinutes, freezeClockAt, renderWithClock } from "../clock.tsx";

freezeClockAt();

const Label = ({ startsAt }: { startsAt: string }) => <p>{useShowStatus(startsAt).label}</p>;
const Time = () => <p>{useNow().toISOString()}</p>;

describe("the clock", () => {
  it("ticks once a minute: a show's label follows the time", () => {
    renderWithClock(<Label startsAt="2026-10-13T12:02:00+03:00" />);
    expect(screen.getByText("alkaa 2 min päästä")).toBeTruthy();
    advanceMinutes(1);
    expect(screen.getByText("alkaa nyt")).toBeTruthy();
    advanceMinutes(1);
    expect(screen.getByText("alkanut")).toBeTruthy();
  });

  it("renders each island at its own request's time on the server, never a previous one", () => {
    const at = (iso: string) =>
      renderToString(
        <ClockIsland now={iso}>
          <Time />
        </ClockIsland>,
      );
    expect(at("2026-10-13T09:00:00.000Z")).toContain("2026-10-13T09:00:00.000Z");
    expect(at("2026-10-13T17:30:00.000Z")).toContain("2026-10-13T17:30:00.000Z");
  });
});
