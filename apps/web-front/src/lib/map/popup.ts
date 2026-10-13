import { fi } from "../text.ts";
import type { VenueProps } from "./geojson.ts";
import * as css from "./popup.css.ts";

/**
 * The popup for a venue pin, built as DOM nodes with `textContent`, so venue names can
 * never inject markup. Links to the venue's own page.
 */
export const popupContent = (venue: VenueProps, doc: Document = document): HTMLElement => {
  const root = doc.createElement("div");
  root.className = css.popup;

  const name = doc.createElement("strong");
  name.className = css.name;
  name.textContent = venue.name;

  const address = doc.createElement("span");
  address.textContent = venue.address || venue.city;

  const link = doc.createElement("a");
  link.href = venue.path;
  link.textContent = fi.venuePage;

  root.append(name, address, link);
  return root;
};
