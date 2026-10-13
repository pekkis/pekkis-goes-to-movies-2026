import { parseDate } from "@internationalized/date";
import { useEffect, useState } from "react";
import {
  Button,
  Calendar,
  CalendarCell,
  CalendarGrid,
  DateInput,
  DatePicker,
  DateSegment,
  Dialog,
  Group,
  Heading,
  I18nProvider,
  Label,
  Popover,
} from "react-aria-components";
import { fi } from "../lib/text.ts";
import { button } from "../styles/recipes/button.css.ts";
import * as css from "./DateNav.css.ts";

type Props = {
  /** The shown day, YYYY-MM-DD. */
  date: string;
  /** Where a chosen day goes; the page's own URL with `?date=`. Tests replace it. */
  navigate?: (url: string) => void;
};

const goTo = (url: string) => window.location.assign(url);

/**
 * Day picker, progressively enhanced. The server (and a browser without JavaScript) gets a
 * plain GET form; once hydrated, React Aria's accessible date picker replaces it.
 */
export const DateNav = ({ date, navigate = goTo }: Props) => {
  const [enhanced, setEnhanced] = useState(false);
  useEffect(() => setEnhanced(true), []);

  if (!enhanced) {
    return (
      <form method="get" className={css.form}>
        <label>
          <span className={css.label}>{fi.date}</span>
          <input className={css.field} type="date" name="date" defaultValue={date} required />
        </label>
        <button type="submit" className={button({ tone: "ghost" })}>
          {fi.show}
        </button>
      </form>
    );
  }

  return (
    <I18nProvider locale="fi-FI">
      <DatePicker
        defaultValue={parseDate(date)}
        onChange={(d) => d && d.toString() !== date && navigate(`?date=${d.toString()}`)}
      >
        <Label className={css.label}>{fi.date}</Label>
        <Group className={css.field}>
          <DateInput>
            {(segment) => <DateSegment className={css.segment} segment={segment} />}
          </DateInput>
          <Button className={button({ tone: "ghost", size: "sm" })} aria-label={fi.openCalendar}>
            ▾
          </Button>
        </Group>
        <Popover className={css.popover}>
          <Dialog>
            <Calendar>
              <header className={css.calendarHeader}>
                <Button
                  slot="previous"
                  className={button({ tone: "ghost", size: "sm" })}
                  aria-label={fi.previousMonth}
                >
                  ‹
                </Button>
                <Heading />
                <Button
                  slot="next"
                  className={button({ tone: "ghost", size: "sm" })}
                  aria-label={fi.nextMonth}
                >
                  ›
                </Button>
              </header>
              <CalendarGrid>
                {(day) => <CalendarCell className={css.cell} date={day} />}
              </CalendarGrid>
            </Calendar>
          </Dialog>
        </Popover>
      </DatePicker>
    </I18nProvider>
  );
};
