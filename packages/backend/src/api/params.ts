import { z } from "@hono/zod-openapi";
import type { Bbox } from "../queries/common.ts";

const NUM = String.raw`-?\d+(?:\.\d+)?`;

/** Parses "minLon,minLat,maxLon,maxLat"; undefined when malformed or inverted. */
export const parseBbox = (raw: string): Bbox | undefined => {
  const parts = raw.split(",").map(Number);
  if (parts.length !== 4 || parts.some((n) => !Number.isFinite(n))) return undefined;
  const [minLon, minLat, maxLon, maxLat] = parts as [number, number, number, number];
  const valid =
    minLon < maxLon &&
    minLat < maxLat &&
    minLat >= -90 &&
    maxLat <= 90 &&
    minLon >= -180 &&
    maxLon <= 180;
  return valid ? { minLon, minLat, maxLon, maxLat } : undefined;
};

export const bboxParam = z
  .string()
  .regex(new RegExp(`^${NUM}(?:,${NUM}){3}$`))
  .refine((v) => parseBbox(v) !== undefined, "min must be below max, within WGS 84 bounds")
  .optional()
  .openapi({
    description: "Map viewport: minLon,minLat,maxLon,maxLat (WGS 84).",
    example: "24.5,60.1,25.3,60.4",
  });

export const dateParam = z.iso.date().optional().openapi({
  description: "Business date, YYYY-MM-DD. Default: today in Helsinki.",
  example: "2026-10-10",
});

export const afterParam = z
  .string()
  .regex(/^([01]\d|2[0-3]):[0-5]\d$/)
  .optional()
  .openapi({
    description: "Only shows starting at or after this Helsinki time (HH:MM).",
    example: "18:00",
  });

export const limitParam = (fallback: number, max: number) =>
  z.coerce
    .number()
    .int()
    .min(1)
    .max(max)
    .default(fallback)
    .openapi({ description: `Page size, at most ${max}.`, example: fallback });

export const idParam = (example: string) =>
  z.object({
    id: z
      .string()
      .min(1)
      .openapi({ param: { name: "id", in: "path" }, example }),
  });
