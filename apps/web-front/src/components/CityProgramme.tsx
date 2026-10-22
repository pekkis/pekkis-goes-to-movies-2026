import type { Screening } from "../lib/api.ts";
import { collapseStarted } from "../lib/show-status.ts";
import { fi } from "../lib/text.ts";
import { ClockIsland, useNow } from "./clock.tsx";
import * as css from "./Programme.css.ts";
import { ScreeningList } from "./ScreeningList.tsx";

/** Started shows wait behind "Näytä alkaneet" while there is still something to come. */
const CityDay = ({ screenings }: { screenings: Screening[] }) => {
  const { collapsed, shown } = collapseStarted(screenings, useNow());
  return (
    <>
      {collapsed.length > 0 && (
        <details className={css.started}>
          <summary>{fi.showStarted(collapsed.length)}</summary>
          <ScreeningList screenings={collapsed} inCity />
        </details>
      )}
      <ScreeningList screenings={shown} inCity />
    </>
  );
};

/**
 * The city page's day, as an island (`client:idle`): rendered on the server at the
 * server's time, then kept current in the browser, so "alkaa 5 min päästä" turns into
 * "alkanut" without a reload.
 */
export const CityProgramme = ({ screenings, now }: { screenings: Screening[]; now: string }) => (
  <ClockIsland now={now}>
    <CityDay screenings={screenings} />
  </ClockIsland>
);
