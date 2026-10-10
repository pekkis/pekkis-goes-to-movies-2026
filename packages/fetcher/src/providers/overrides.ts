import { readFile } from "node:fs/promises";
import { Id, type ProviderBatch } from "@pgtm/model";
import { z } from "zod";
import { FinnishGeo, GeoSource } from "../geo/geo.ts";

/**
 * Hand-maintained fixes to venue data a provider gets wrong or leaves out (committed).
 * Config-based platforms (Nexxo, eTiketti) put these in their sites.ts instead; this is
 * for chains whose venues come from their API. Counterpart of tmdb-aliases.json.
 */
export const VenueOverrides = z.record(
  Id,
  z
    .object({
      /** The venue's name, so that the file is readable. */
      name: z.string(),
      address: z.string().optional(),
      postalCode: z
        .string()
        .regex(/^\d{5}$/)
        .optional(),
      geo: FinnishGeo.optional(),
      geoSource: GeoSource.optional(),
      /** Why: what was wrong, how it was checked. */
      note: z.string(),
    })
    .refine((o) => !o.geo || o.geoSource, { message: "geo needs a geoSource" }),
);
export type VenueOverrides = z.infer<typeof VenueOverrides>;

export const VENUE_OVERRIDES_PATH = new URL("../../config/venue-overrides.json", import.meta.url);

export const loadVenueOverrides = async (
  path: URL | string = VENUE_OVERRIDES_PATH,
): Promise<VenueOverrides> => VenueOverrides.parse(JSON.parse(await readFile(path, "utf8")));

/** Pure: patches the batch's venues and warns about venues still without coordinates. */
export const finishVenues = (batch: ProviderBatch, overrides: VenueOverrides): ProviderBatch => {
  const venues = batch.venues.map((venue) => {
    const o = overrides[venue.id];
    if (!o) return venue;
    return {
      ...venue,
      ...(o.address && { address: o.address }),
      ...(o.postalCode && { postalCode: o.postalCode }),
      ...(o.geo && { geo: o.geo }),
    };
  });
  const missing = venues
    .filter((v) => !v.geo)
    .map((v) => ({
      code: "venue-without-geo",
      message: `${v.name} (${v.city}) has no coordinates; see pnpm venues:locate`,
      context: { venueId: v.id },
    }));
  return { ...batch, venues, warnings: [...batch.warnings, ...missing] };
};
