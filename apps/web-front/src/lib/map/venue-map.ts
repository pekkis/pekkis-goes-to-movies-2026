// Browser-only: draws the venue map. Loaded by /fi/kartta's <script>, never on the server.
import {
  Map as MapLibreMap,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type GeoJSONSource,
  type MapGeoJSONFeature,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre looks for its worker next to its own file, which bundling moves: hand Vite the
// (self-contained) worker as an asset and tell MapLibre where it went.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { vars } from "../../styles/theme.css.ts";
import { boundsOf, type VenueCollection, type VenueProps } from "./geojson.ts";
import { localizeLabels } from "./labels.ts";
import { popupContent } from "./popup.ts";

/** OpenFreeMap: free, no key, no limits; MapLibre adds its required attribution. */
const STYLES = {
  light: "https://tiles.openfreemap.org/styles/positron",
  dark: "https://tiles.openfreemap.org/styles/dark",
} as const;

const SOURCE = "venues";
/** Mainland Finland, if there are no venues to fit. */
const FINLAND: [number, number, number, number] = [20.5, 59.7, 31.6, 70.1];

type Scheme = keyof typeof STYLES;

/** Our theme: `<html data-theme>` wins, otherwise the OS setting. */
const scheme = (): Scheme => {
  const chosen = document.documentElement.dataset.theme;
  if (chosen === "light" || chosen === "dark") return chosen;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

/** A theme token's current value: vars hold `var(--name)`, the map needs the color. */
const token = (el: HTMLElement, cssVar: string) =>
  getComputedStyle(el).getPropertyValue(cssVar.slice(4, -1)).trim();

const addVenueLayers = (map: MapLibreMap, el: HTMLElement, venues: VenueCollection) => {
  const accent = token(el, vars.color.accent);
  const onAccent = token(el, vars.color.accentText);
  const ring = token(el, vars.color.surface);

  map.addSource(SOURCE, {
    type: "geojson",
    data: venues,
    cluster: true,
    clusterRadius: 48,
    clusterMaxZoom: 12,
  });
  map.addLayer({
    id: "clusters",
    type: "circle",
    source: SOURCE,
    filter: ["has", "point_count"],
    paint: {
      "circle-color": accent,
      "circle-radius": ["step", ["get", "point_count"], 16, 5, 20, 15, 26],
      "circle-stroke-width": 2,
      "circle-stroke-color": ring,
    },
  });
  map.addLayer({
    id: "cluster-count",
    type: "symbol",
    source: SOURCE,
    filter: ["has", "point_count"],
    layout: {
      "text-field": ["get", "point_count_abbreviated"],
      "text-font": ["Noto Sans Regular"],
      "text-size": 13,
    },
    paint: { "text-color": onAccent },
  });
  map.addLayer({
    id: "venue",
    type: "circle",
    source: SOURCE,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": accent,
      "circle-radius": 8,
      "circle-stroke-width": 2,
      "circle-stroke-color": ring,
    },
  });
};

const pointOf = (f: MapGeoJSONFeature) =>
  (f.geometry as { coordinates: [number, number] }).coordinates;

export const mountVenueMap = (el: HTMLElement, venues: VenueCollection): MapLibreMap => {
  setWorkerUrl(workerUrl);
  let current = scheme();
  const map = new MapLibreMap({
    container: el,
    bounds: boundsOf(venues) ?? FINLAND,
    fitBoundsOptions: { padding: 48 },
    cooperativeGestures: true, // scrolling the page doesn't zoom the map by accident
  });
  map.addControl(new NavigationControl({ showCompass: false }));
  const load = (s: Scheme) =>
    map.setStyle(STYLES[s], { transformStyle: (_, next) => localizeLabels(next, "fi") });
  load(current);

  // Our layers are part of the style: re-add them whenever the style (re)loads.
  map.on("style.load", () => addVenueLayers(map, el, venues));

  map.on("click", "clusters", async (e) => {
    const cluster = e.features?.[0];
    const id = cluster?.properties?.["cluster_id"];
    if (!cluster || typeof id !== "number") return;
    const zoom = await map.getSource<GeoJSONSource>(SOURCE)!.getClusterExpansionZoom(id);
    map.easeTo({ center: pointOf(cluster), zoom });
  });

  map.on("click", "venue", (e) => {
    const venue = e.features?.[0];
    if (!venue) return;
    new Popup({ offset: 12, maxWidth: "18rem" })
      .setLngLat(pointOf(venue))
      .setDOMContent(popupContent(venue.properties as VenueProps))
      .addTo(map);
  });

  for (const layer of ["clusters", "venue"]) {
    map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
  }

  // Follow the OS switching between light and dark.
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    const next = scheme();
    if (next !== current) load((current = next));
  });

  return map;
};
