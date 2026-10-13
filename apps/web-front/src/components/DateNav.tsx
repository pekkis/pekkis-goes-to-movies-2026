import { fi } from "../lib/text.ts";
import { addDays } from "../lib/time.ts";
import { button } from "../styles/recipes/button.css.ts";
import * as css from "./DateNav.css.ts";

/**
 * Day navigation: previous and next day as links, and a plain GET form with the browser's
 * own date input. No JavaScript; phones show their system picker, and accessibility comes
 * from the browser. Links and form keep the current path and only change `?date=`.
 */
export const DateNav = ({ date }: { date: string }) => (
  <nav className={css.nav} aria-label={fi.date}>
    <a href={`?date=${addDays(date, -1)}`}>‹ {fi.previousDay}</a>
    <form method="get" className={css.form}>
      <label>
        <span className={css.label}>{fi.date}</span>
        <input className={css.field} type="date" name="date" defaultValue={date} required />
      </label>
      <button type="submit" className={button({ tone: "ghost" })}>
        {fi.show}
      </button>
    </form>
    <a href={`?date=${addDays(date, 1)}`}>{fi.nextDay} ›</a>
  </nav>
);
