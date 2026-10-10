/**
 * Types for API clients in this workspace (React):
 *   import { hc } from "hono/client";
 *   import type { AppType } from "@pgtm/backend";
 *   const api = hc<AppType>("https://…");
 *   const res = await api.v1.screenings.$get({ query: { date: "2026-10-10" } });
 */
export type { AppType } from "./api/app.ts";
