import type { StyleSpecification } from "maplibre-gl";

/** Mentions a name property: those labels are localized, others (road numbers) are kept. */
const namesPlace = (value: unknown): boolean => JSON.stringify(value ?? null).includes('"name');

/**
 * Map labels in `lang` where the tiles have it ("Tukholma", "Pohjanlahti"), else the
 * Latin-script name, else the local one. OpenFreeMap's styles default to English.
 */
export const localizeLabels = (style: StyleSpecification, lang: string): StyleSpecification => ({
  ...style,
  layers: style.layers.map((layer) =>
    layer.type === "symbol" && namesPlace(layer.layout?.["text-field"])
      ? {
          ...layer,
          layout: {
            ...layer.layout,
            "text-field": [
              "coalesce",
              ["get", `name:${lang}`],
              ["get", "name:latin"],
              ["get", "name"],
            ],
          },
        }
      : layer,
  ),
});
