import type { ReactNode } from "react";
import { RADII_KM, type SearchPage } from "../lib/search.ts";
import { fi } from "../lib/text.ts";
import { formatShortDay } from "../lib/time.ts";
import { button } from "../styles/recipes/button.css.ts";
import * as css from "./Search.css.ts";

/**
 * The search page's query: days, place and an optional film name, as a plain GET form.
 * Rendered on the server; it works without JavaScript. `locate` is the "use my location"
 * island, passed by the page as a named slot (Astro hands it over as this prop).
 */
export const SearchForm = ({ page, locate }: { page: SearchPage; locate?: ReactNode }) => {
  const { params, place } = page;
  const here = place?.kind === "here" ? place.point : params.here;
  return (
    <form method="get" action="/fi/haku" className={css.form}>
      <fieldset className={css.fieldset}>
        <legend className={css.legend}>{fi.days}</legend>
        <div className={css.choices}>
          {page.dayOptions.map((day, i) => (
            <label key={day} className={css.choice}>
              <input
                type="checkbox"
                name="paiva"
                value={day}
                defaultChecked={params.days.includes(day)}
              />
              {i === 0 ? `${fi.today} ${formatShortDay(day)}` : formatShortDay(day)}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className={css.fieldset}>
        <legend className={css.legend}>{fi.place}</legend>
        <div className={css.choices}>
          <select
            name="kaupunki"
            className={css.field}
            defaultValue={place?.kind === "city" ? place.slug : ""}
          >
            <option value="">{here ? fi.myLocation : fi.chooseCity}</option>
            {page.cities.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
          {locate}
          <label className={css.choice}>
            {fi.radius}{" "}
            <select name="sade" className={css.field} defaultValue={String(params.radiusKm)}>
              {RADII_KM.map((km) => (
                <option key={km} value={km}>
                  {fi.km(km)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {here && (
          <>
            <input type="hidden" name="lat" value={here.lat.toFixed(4)} />
            <input type="hidden" name="lon" value={here.lon.toFixed(4)} />
          </>
        )}
      </fieldset>

      <label className={css.fieldset}>
        <span className={css.legend}>{fi.filmName}</span>
        <input
          type="search"
          name="elokuva"
          className={css.field}
          defaultValue={params.film ?? ""}
          placeholder={fi.filmExample}
        />
      </label>

      <div>
        <button type="submit" className={button()}>
          {fi.search}
        </button>
      </div>
    </form>
  );
};
