import { act, cleanup, render } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, vi } from "vitest";
import { NowProvider } from "../src/components/now.tsx";
import { NOON } from "./fixtures.ts";

/** Fake timers with the clock at noon on the fixtures' day, around every test in the file. */
export const useFixedClock = (now: Date = NOON): void => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });
};

/** Render inside a `<NowProvider>` started at the (fake) current time. */
export const renderWithClock = (ui: ReactNode) =>
  render(<NowProvider initial={new Date().toISOString()}>{ui}</NowProvider>);

/** Move the fake clock forward, letting the provider's minute timer fire. */
export const advanceMinutes = (minutes: number) =>
  act(() => {
    vi.advanceTimersByTime(minutes * 60_000);
  });
