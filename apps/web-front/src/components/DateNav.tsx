import { fi } from "../lib/text.ts";
import { button } from "../styles/recipes/button.css.ts";
import * as css from "./DateNav.css.ts";

/**
 * Day picker: a plain GET form with the browser's own date input. No JavaScript; phones
 * show their system picker, and accessibility comes from the browser.
 */
export const DateNav = ({ date }: { date: string }) => (
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
