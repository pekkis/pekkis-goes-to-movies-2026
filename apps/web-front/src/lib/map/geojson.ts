import { venuePath } from "../venues.ts";

/** What a map pin knows about its venue; everything the popup shows. */
export type VenueProps = { name: string; city: string; address: string; path: string };

export type VenueFeature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [lon: number, lat: number] };
  properties: VenueProps;
};

export type VenueCollection = { type: "FeatureCollection"; features: VenueFeature[] };

type MappableVenue = {
  name: string;
  city: string;
  address: string | null;
  postalCode: string | null;
  geo: { lat: number; lon: number } | null;
};

/** Venues as GeoJSON points (lon, lat order); venues without coordinates are left out. */
export const venuesToGeoJson = (venues: readonly MappableVenue[]): VenueCollection => ({
  type: "FeatureCollection",
  features: venues.flatMap((v) =>
    v.geo
      ? [
          {
            type: "Feature" as const,
            geometry: { type: "Point" as const, coordinates: [v.geo.lon, v.geo.lat] },
            properties: {
              name: v.name,
              city: v.city,
              address: [v.address, [v.postalCode, v.city].filter(Boolean).join(" ")]
                .filter(Boolean)
                .join(", "),
              path: venuePath(v),
            },
          },
        ]
      : [],
  ),
});

/** [west, south, east, north] around every point, for the map's first view. */
export const boundsOf = (
  collection: VenueCollection,
): [number, number, number, number] | undefined => {
  const points = collection.features.map((f) => f.geometry.coordinates);
  if (!points.length) return undefined;
  const lons = points.map(([lon]) => lon);
  const lats = points.map(([, lat]) => lat);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
};
