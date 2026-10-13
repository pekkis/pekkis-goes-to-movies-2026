import { act, cleanup, render } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, vi } from "vitest";
import { ClockIsland } from "../src/components/clock.tsx";
import { currentInstant } from "@pgtm/model/time";
import { NOON } from "./fixtures.ts";

/** Fake timers with the clock at `now` (default: noon on the fixtures' day), around every test in the file. */
export const freezeClockAt = (now: Date = NOON): void => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });
};

/** Render inside a `<ClockIsland>` started at the (fake) current time. */
export const renderWithClock = (ui: ReactNode) =>
  render(<ClockIsland now={currentInstant().toString()}>{ui}</ClockIsland>);

/** Move the fake clock forward, letting the provider's minute timer fire. */
export const advanceMinutes = (minutes: number) =>
  act(() => {
    vi.advanceTimersByTime(minutes * 60_000);
  });
