import { fi } from "./text.ts";

/** A show counts as "soon" this many minutes before it starts. */
export const SOON_MINUTES = 60;
/** Ticket links stay this long after the start: cinemas often sell during the ads. */
export const TICKETS_AFTER_START_MINUTES = 15;

export type ShowState = "started" | "soon" | "later";

export type ShowStatus = {
  state: ShowState;
  /** Shown next to the time: "alkanut", "alkaa 25 min päästä", or nothing. */
  label: string;
  /** Whether to offer the ticket link (if the cinema gave one). */
  ticketsOpen: boolean;
};

const MINUTE = 60_000;

/**
 * Where a show stands at `now`. Compares instants, so shows after midnight and other days
 * just work: a past day's shows have all started, a future day's are all later. Used by
 * the server when rendering and by the browser script that keeps an open page current.
 */
export const showStatus = (startsAt: string | Date, now: Date): ShowStatus => {
  const minutes = Math.ceil((new Date(startsAt).getTime() - now.getTime()) / MINUTE);
  if (minutes <= 0) {
    return {
      state: "started",
      label: fi.started,
      ticketsOpen: -minutes < TICKETS_AFTER_START_MINUTES,
    };
  }
  if (minutes <= SOON_MINUTES)
    return { state: "soon", label: fi.startsIn(minutes), ticketsOpen: true };
  return { state: "later", label: "", ticketsOpen: true };
};

/**
 * Started shows go behind "Näytä alkaneet" so the rest of the day comes first; but when
 * nothing is left to come (a past day, a late evening), everything is shown as it is.
 */
export const collapseStarted = <S extends { startsAt: string }>(
  screenings: readonly S[],
  now: Date,
): { collapsed: S[]; shown: S[] } => {
  const started = screenings.filter((s) => showStatus(s.startsAt, now).state === "started");
  const coming = screenings.filter((s) => showStatus(s.startsAt, now).state !== "started");
  return coming.length
    ? { collapsed: started, shown: coming }
    : { collapsed: [], shown: [...screenings] };
};
