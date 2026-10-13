import "../lib/temporal.ts";
import { currentInstant } from "@pgtm/model/time";
import { atom, Provider, useAtomValue } from "jotai";
import { useHydrateAtoms } from "jotai/utils";
import type { ReactNode } from "react";
import { showStatus, type ShowStatus } from "../lib/show-status.ts";

/** The current time. While anything reads it, it ticks once a minute. */
export const nowAtom = atom(currentInstant());
nowAtom.onMount = (setNow) => {
  setNow(currentInstant());
  const timer = setInterval(() => setNow(currentInstant()), 60_000);
  return () => clearInterval(timer);
};

const StartAt = ({ now, children }: { now: string; children: ReactNode }) => {
  useHydrateAtoms([[nowAtom, Temporal.Instant.from(now)]]);
  return children;
};

/**
 * The root of an island that shows showtimes. Its own jotai store starts at `now`, the
 * server's time (an ISO string, so it can cross into an island): the server renders at that
 * time, hydration matches it, and then the browser's clock takes over. Per island and per
 * request, so one request's time never leaks into another on the server.
 */
export const ClockIsland = ({ now, children }: { now: string; children: ReactNode }) => (
  <Provider>
    <StartAt now={now}>{children}</StartAt>
  </Provider>
);

/** The current time, ticking once a minute. */
export const useNow = (): Temporal.Instant => useAtomValue(nowAtom);

/** A show's live status: started, soon or later; its label; whether tickets are sold. */
export const useShowStatus = (startsAt: string): ShowStatus => showStatus(startsAt, useNow());
