import { useState } from "react";
import { fi } from "../lib/text.ts";
import { button } from "../styles/recipes/button.css.ts";

/** Sets a form's field by name, adding a hidden one if the form has none yet. */
const setField = (form: HTMLFormElement, name: string, value: string) => {
  const existing = form.elements.namedItem(name);
  if (existing instanceof HTMLInputElement || existing instanceof HTMLSelectElement) {
    existing.value = value;
    return;
  }
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = name;
  input.value = value;
  form.append(input);
};

/**
 * "Käytä sijaintiani": asks the browser for its location, puts it into the search form
 * (clearing the city, which would otherwise win) and submits. An island (`client:idle`);
 * without JavaScript or permission, the city choice is there.
 */
export const LocateButton = () => {
  const [state, setState] = useState<"idle" | "locating" | "failed">("idle");
  return (
    <>
      <button
        type="button"
        className={button({ tone: "ghost" })}
        disabled={state === "locating"}
        onClick={(event) => {
          const form = event.currentTarget.form;
          if (!form || !("geolocation" in navigator)) {
            setState("failed");
            return;
          }
          setState("locating");
          navigator.geolocation.getCurrentPosition(
            ({ coords }) => {
              setField(form, "lat", coords.latitude.toFixed(4));
              setField(form, "lon", coords.longitude.toFixed(4));
              setField(form, "kaupunki", "");
              form.requestSubmit();
            },
            () => setState("failed"),
            { maximumAge: 600_000, timeout: 15_000 },
          );
        }}
      >
        {state === "locating" ? fi.locating : fi.locateMe}
      </button>
      {state === "failed" && <span role="status">{fi.locationFailed}</span>}
    </>
  );
};
