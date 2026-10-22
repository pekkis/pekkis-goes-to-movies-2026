import type { KindsPage } from "../lib/kinds.ts";
import { fi } from "../lib/text.ts";
import { formatDay } from "../lib/time.ts";
import { ClockIsland } from "./clock.tsx";
import * as css from "./Search.css.ts";
import { ScreeningList } from "./ScreeningList.tsx";

/**
 * The chosen kinds' screenings, day by day, as an island (`client:idle`): the live
 * showtime status ("alkaa 30 min päästä") stays current while the page is open.
 */
export const KindsProgramme = ({ days, now }: { days: KindsPage["days"]; now: string }) => (
  <ClockIsland now={now}>
    {days.length === 0 ? (
      <p>{fi.noKindScreenings}</p>
    ) : (
      days.map((day) => (
        <section key={day.date}>
          <h2 className={css.dayHeading}>{formatDay(day.date)}</h2>
          <ScreeningList screenings={day.screenings} showSeries />
        </section>
      ))
    )}
  </ClockIsland>
);
