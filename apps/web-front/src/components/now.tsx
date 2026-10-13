import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { showStatus, type ShowStatus } from "../lib/show-status.ts";

const NowContext = createContext<Date | null>(null);

/**
 * One shared clock for everything inside it, re-rendering once a minute. `initial` is the
 * server's time (an ISO string, so it can cross into an island): the first client render
 * then matches the server's HTML, and the clock follows the real time from there.
 * Wrap each island that shows showtimes in one of these.
 */
export const NowProvider = ({ initial, children }: { initial: string; children: ReactNode }) => {
  const [now, setNow] = useState(() => new Date(initial));
  useEffect(() => {
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);
  return <NowContext value={now}>{children}</NowContext>;
};

/** The current time from the nearest `<NowProvider>`. */
export const useCurrentTime = (): Date => {
  const now = useContext(NowContext);
  if (!now) throw new Error("useCurrentTime needs a <NowProvider> around it");
  return now;
};

/** A show's live status: started, soon or later; its label; whether tickets are sold. */
export const useShowStatus = (startsAt: string): ShowStatus =>
  showStatus(startsAt, useCurrentTime());
