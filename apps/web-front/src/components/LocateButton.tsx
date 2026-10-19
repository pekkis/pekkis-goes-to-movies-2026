import { useRef, useState } from "react";
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
 * How long we wait for the browser at most. Its own `timeout` starts only once permission
 * is given, so a permission prompt that is closed or ignored (Firefox), or a system that
 * never answers (macOS with location services off for the browser), would leave the
 * button "locating" forever without this (seen on the live site, 2026-10-19).
 */
export const LOCATE_WATCHDOG_MS = 20_000;

type State = "idle" | "locating" | "found" | "denied" | "unavailable" | "timeout";

const MESSAGES: Partial<Record<State, string>> = {
  found: fi.locationFound,
  denied: fi.locationDenied,
  unavailable: fi.locationUnavailable,
  timeout: fi.locationTimeout,
};

/**
 * "Käytä sijaintiani": asks the browser for its location and puts it into the search form,
 * clearing the city (which would otherwise win) and naming the place "Oma sijainti". Like
 * choosing a city, it does not submit: the days and radius can still change before "Hae".
 * It always ends, found or with a message saying why not, and it can be pressed again.
 * An island (`client:idle`); without JavaScript or permission, the city choice is there.
 */
export const LocateButton = () => {
  const [state, setState] = useState<State>("idle");
  // Each press gets a number; an answer to an earlier press, or after the watchdog, is ignored.
  const attempt = useRef(0);

  const locate = (form: HTMLFormElement) => {
    const id = ++attempt.current;
    const current = () => attempt.current === id;
    setState("locating");
    const watchdog = setTimeout(() => {
      if (current()) {
        attempt.current++;
        setState("timeout");
      }
    }, LOCATE_WATCHDOG_MS);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        clearTimeout(watchdog);
        if (!current()) {
          return;
        }
        setField(form, "lat", coords.latitude.toFixed(4));
        setField(form, "lon", coords.longitude.toFixed(4));
        setField(form, "kaupunki", "");
        // The empty choice is the place now: say so in the list itself.
        const city = form.elements.namedItem("kaupunki");
        if (city instanceof HTMLSelectElement && city.options[0]) {
          city.options[0].text = fi.myLocation;
        }
        setState("found");
      },
      (error) => {
        clearTimeout(watchdog);
        if (current()) {
          // 1 PERMISSION_DENIED, 2 POSITION_UNAVAILABLE, 3 TIMEOUT.
          setState(error.code === 1 ? "denied" : error.code === 3 ? "timeout" : "unavailable");
        }
      },
      // A fix from the last ten minutes will do, and Wi-Fi accuracy is plenty for a radius.
      { maximumAge: 600_000, timeout: 15_000, enableHighAccuracy: false },
    );
  };

  const message = MESSAGES[state];
  return (
    <>
      <button
        type="button"
        className={button({ tone: "ghost" })}
        aria-busy={state === "locating" || undefined}
        onClick={(event) => {
          const form = event.currentTarget.form;
          if (!form || !("geolocation" in navigator)) {
            setState("unavailable");
            return;
          }
          // Pressing again while waiting starts over; the earlier request is ignored.
          locate(form);
        }}
      >
        {state === "locating" ? fi.locating : fi.locateMe}
      </button>
      {message && <span role="status">{message}</span>}
    </>
  );
};
