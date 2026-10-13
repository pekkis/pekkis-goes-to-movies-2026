import type { Screening } from "../lib/api.ts";
import { collapseStarted } from "../lib/show-status.ts";
import { fi } from "../lib/text.ts";
import { NowProvider, useCurrentTime } from "./now.tsx";
import * as css from "./Programme.css.ts";
import { ScreeningList } from "./ScreeningList.tsx";

/** Started shows wait behind "Näytä alkaneet" while there is still something to come. */
const CityDay = ({ screenings }: { screenings: Screening[] }) => {
  const { collapsed, shown } = collapseStarted(screenings, useCurrentTime());
  return (
    <>
      {collapsed.length > 0 && (
        <details className={css.started}>
          <summary>{fi.showStarted(collapsed.length)}</summary>
          <ScreeningList screenings={collapsed} />
        </details>
      )}
      <ScreeningList screenings={shown} />
    </>
  );
};

/**
 * The city page's day, as an island (`client:idle`): rendered on the server at the
 * server's time, then kept current in the browser, so "alkaa 5 min päästä" turns into
 * "alkanut" without a reload.
 */
export const CityProgramme = ({ screenings, now }: { screenings: Screening[]; now: string }) => (
  <NowProvider initial={now}>
    <CityDay screenings={screenings} />
  </NowProvider>
);
