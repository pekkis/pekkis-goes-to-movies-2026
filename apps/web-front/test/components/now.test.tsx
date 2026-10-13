// @vitest-environment happy-dom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useCurrentTime, useShowStatus } from "../../src/components/now.tsx";
import { advanceMinutes, renderWithClock, useFixedClock } from "../clock.tsx";

useFixedClock();

const Label = ({ startsAt }: { startsAt: string }) => <p>{useShowStatus(startsAt).label}</p>;

describe("NowProvider", () => {
  it("ticks once a minute: a show's label follows the clock", () => {
    renderWithClock(<Label startsAt="2026-10-13T12:02:00+03:00" />);
    expect(screen.getByText("alkaa 2 min päästä")).toBeTruthy();
    advanceMinutes(1);
    expect(screen.getByText("alkaa nyt")).toBeTruthy();
    advanceMinutes(1);
    expect(screen.getByText("alkanut")).toBeTruthy();
  });

  it("is required: the hooks fail loudly without a provider", () => {
    const Bare = () => <p>{useCurrentTime().toISOString()}</p>;
    expect(() => render(<Bare />)).toThrow(/NowProvider/);
  });
});
