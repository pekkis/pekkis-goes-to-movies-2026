import type { KindsPage } from "../lib/kinds.ts";
import { TAG_CHOICES } from "../lib/kinds.ts";
import { fi, TAG_GROUP_NAMES, TAG_NAMES } from "../lib/text.ts";
import { formatShortDay } from "../lib/time.ts";
import { button } from "../styles/recipes/button.css.ts";
import * as css from "./Search.css.ts";

/**
 * The special screenings page's choices: every screening tag by group, and the series with
 * screenings in the coming weeks, as checkboxes in a plain GET form. Rendered on the
 * server; works without JavaScript, and the resulting address is the shareable one.
 */
export const KindsForm = ({ page }: { page: KindsPage }) => (
  <form method="get" action="/fi/erikoisnaytokset" className={css.form}>
    <fieldset className={css.fieldset}>
      <legend className={css.legend}>{fi.kindsOfScreening}</legend>
      {TAG_CHOICES.map(({ group, tags }) => (
        <div key={group} className={css.choices}>
          <span className={css.muted}>{TAG_GROUP_NAMES[group]}</span>
          {tags.map((tag) => (
            <label key={tag} className={css.choice}>
              <input
                type="checkbox"
                name="tunniste"
                value={tag}
                defaultChecked={page.params.tags.includes(tag)}
              />
              {TAG_NAMES[tag]}
            </label>
          ))}
        </div>
      ))}
    </fieldset>

    <fieldset className={css.fieldset}>
      <legend className={css.legend}>{fi.seriesHeading}</legend>
      {page.series.length > 0 ? (
        <div className={css.choices}>
          {page.series.map((s) => (
            <label key={s.id} className={css.choice}>
              <input
                type="checkbox"
                name="sarja"
                value={s.id}
                defaultChecked={page.params.series.includes(s.id)}
              />
              {s.name}
              {s.screenings > 0 && (
                <span className={css.count}>
                  {fi.seriesUpcoming(s.screenings, formatShortDay(s.firstDay))}
                </span>
              )}
            </label>
          ))}
        </div>
      ) : (
        <p>{fi.noSeries}</p>
      )}
    </fieldset>

    <div>
      <button type="submit" className={button()}>
        {fi.show}
      </button>
    </div>
  </form>
);
